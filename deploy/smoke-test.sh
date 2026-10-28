#!/usr/bin/env bash
# End-to-end test of the production stack (Vue app and API) behind nginx, using a throwaway self-signed
# certificate and an isolated compose project. Runs locally and in CI:
#
#   bash deploy/smoke-test.sh            # HTTP_PORT/HTTPS_PORT default to 8080/8443
#
# Exits non-zero if any check fails. Everything it creates is removed on exit.
set -euo pipefail
cd "$(dirname "$0")/.."

work=$(mktemp -d)
export COMPOSE_PROJECT_NAME=listlinkedin-smoke
export SERVER_NAME=go.example.test
export PUBLIC_BASE_URL="https://$SERVER_NAME" DJANGO_ALLOWED_HOSTS="$SERVER_NAME"
export DJANGO_SECRET_KEY="$(openssl rand -base64 48)"
export POSTGRES_DB=smoke POSTGRES_USER=smoke POSTGRES_PASSWORD="$(openssl rand -hex 16)"
export TLS_CERT_DIR="$work/certs" ACME_WEBROOT="$work/acme"
export HTTP_PORT="${HTTP_PORT:-8080}" HTTPS_PORT="${HTTPS_PORT:-8443}"

compose() { docker compose -f compose.prod.yaml "$@"; }
cleanup() {
    if [[ ${failures:-1} -ne 0 ]]; then compose logs --no-color --tail=50 || true; fi
    compose down -v --remove-orphans >/dev/null 2>&1 || true
    rm -rf "$work"
}
trap cleanup EXIT

mkdir -p "$work/certs" "$work/acme"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=$SERVER_NAME" \
    -addext "subjectAltName=DNS:$SERVER_NAME" \
    -keyout "$work/certs/privkey.pem" -out "$work/certs/fullchain.pem" 2>/dev/null

compose up --build -d

https="https://$SERVER_NAME:$HTTPS_PORT"
http="http://$SERVER_NAME:$HTTP_PORT"
curl_() {
    curl -sS --resolve "$SERVER_NAME:$HTTPS_PORT:127.0.0.1" \
        --resolve "$SERVER_NAME:$HTTP_PORT:127.0.0.1" \
        --cacert "$work/certs/fullchain.pem" "$@"
}
json() { python3 -c "import json,sys; print(json.load(sys.stdin)$1)"; }

failures=0
check() {  # check <description> <expected> <actual>
    if [[ "$3" == "$2" ]]; then echo "ok    $1"; else
        echo "FAIL  $1: expected '$2', got '$3'"; failures=$((failures + 1))
    fi
}

echo "Waiting for nginx and the API..."
for _ in $(seq 60); do
    [[ "$(curl_ -o /dev/null -w '%{http_code}' "$https/healthz" 2>/dev/null)" == 200 ]] && break
    sleep 2
done

check "health check over HTTPS" 200 "$(curl_ -o /dev/null -w '%{http_code}' "$https/healthz")"
check "HTTP redirects to HTTPS" "301 https://$SERVER_NAME/api/v1/lists/" \
    "$(curl_ -o /dev/null -w '%{http_code} %{redirect_url}' "$http/api/v1/lists/")"

created=$(curl_ -X POST "$https/api/v1/lists/" -H 'Content-Type: application/json' \
    -d '{"title":"smoke"}')
code=$(json '["public_code"]' <<<"$created")
token=$(json '["owner_token"]' <<<"$created")
check "public URL uses PUBLIC_BASE_URL" "$PUBLIC_BASE_URL/l/$code" "$(json '["public_url"]' <<<"$created")"

link=$(curl_ -X POST "$https/api/v1/lists/$code/links/" -H "Authorization: Bearer $token" \
    -H 'Content-Type: application/json' -d '{"destination_url":"https://example.com/smoke"}')
short_path=$(json '["short_url"]' <<<"$link" | sed "s#^$PUBLIC_BASE_URL##")
check "short URL redirects through the proxy" "302 https://example.com/smoke" \
    "$(curl_ -o /dev/null -w '%{http_code} %{redirect_url}' "$https$short_path")"

headers=$(curl_ -sI "$https/api/v1/lists/$code/" | tr -d '\r' | tr 'A-Z' 'a-z')
check "HSTS header from Django" "strict-transport-security: max-age=31536000; includesubdomains" \
    "$(grep '^strict-transport-security' <<<"$headers")"
check "nginx hides its version" "server: nginx" "$(grep '^server:' <<<"$headers")"

page=$(curl_ "$https/l/$code")
check "public list URL serves the app" 1 "$(grep -c '<div id="app"></div>' <<<"$page")"
page_headers=$(curl_ -sI "$https/l/$code" | tr -d '\r' | tr 'A-Z' 'a-z')
check "app page sends HSTS" "strict-transport-security: max-age=31536000; includesubdomains" \
    "$(grep '^strict-transport-security' <<<"$page_headers")"
check "app page never leaks its URL as a referrer" "referrer-policy: no-referrer" \
    "$(grep '^referrer-policy' <<<"$page_headers")"
check "app page sends a CSP" 1 "$(grep -c "^content-security-policy: default-src 'self'" <<<"$page_headers")"
asset=$(grep -o '/assets/index-[^"]*\.js' <<<"$page")
check "fingerprinted assets are cached immutably" "cache-control: public, max-age=31536000, immutable" \
    "$(curl_ -sI "$https$asset" | tr -d '\r' | tr 'A-Z' 'a-z' | grep '^cache-control')"
check "missing asset is a 404, not the app" 404 \
    "$(curl_ -o /dev/null -w '%{http_code}' "$https/assets/missing.js")"

check "unknown Host header is dropped" 000 \
    "$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: evil.example' "http://127.0.0.1:$HTTP_PORT/" || true)"
check "TLS for unknown names is refused" 000 \
    "$(curl -sk -o /dev/null -w '%{http_code}' "https://127.0.0.1:$HTTPS_PORT/" || true)"
check "oversized body rejected by nginx" 413 \
    "$(head -c 40000 /dev/zero | curl_ -o /dev/null -w '%{http_code}' -X POST \
        "$https/api/v1/lists/" -H 'Content-Type: application/json' --data-binary @-)"

# 1 list was created above; the limit is 30/hour per client. A fresh spoofed
# X-Forwarded-For on every request must not reset it: nginx overwrites the header.
statuses=$(for i in $(seq 30); do
    curl_ -o /dev/null -w '%{http_code}\n' -X POST "$https/api/v1/lists/" \
        -H "X-Forwarded-For: 198.51.100.$i" -H 'Content-Type: application/json' -d '{"title":"t"}'
done | sort | uniq -c | awk '{print $2 "x" $1}' | paste -sd' ')
check "spoofed X-Forwarded-For cannot bypass rate limits" "201x29 429x1" "$statuses"

# `compose port` prints ":0" for a port that is exposed but has no host binding.
published=$(compose port api 8000 2>/dev/null || true)
check "API port is not published" "not published" \
    "$([[ -z "$published" || "$published" == ":0" ]] && echo "not published" || echo "$published")"

echo
if [[ $failures -eq 0 ]]; then echo "All smoke checks passed."; else echo "$failures check(s) failed."; fi
exit "$failures"
