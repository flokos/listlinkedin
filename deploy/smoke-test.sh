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
# Its own maintenance switch: the checkout's deploy/maintenance may serve a real stack.
export MAINTENANCE_DIR="$work/maintenance"

compose() { docker compose -f compose.prod.yaml "$@"; }
cleanup() {
    if [[ ${failures:-1} -ne 0 ]]; then compose logs --no-color --tail=50 || true; fi
    compose down -v --remove-orphans >/dev/null 2>&1 || true
    rm -rf "$work"
}
trap cleanup EXIT

mkdir -p "$work/certs" "$work/acme" "$work/maintenance"
cp deploy/maintenance/maintenance.html "$work/maintenance/"
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
check "HTTP redirects pages to HTTPS" "301 https://$SERVER_NAME/lists" \
    "$(curl_ -o /dev/null -w '%{http_code} %{redirect_url}' "$http/lists")"
check "HTTP API requests are refused, not redirected" 403 \
    "$(curl_ -o /dev/null -w '%{http_code}' "$http/api/v1/lists/")"

# Anonymous creation is retired in production (docs/v2/adr/ADR-011), so seed a legacy
# (edit-link) list with the service V1 used and test the rest of the V1 API on it.
check "anonymous list creation is retired" 410 \
    "$(curl_ -o /dev/null -w '%{http_code}' -X POST "$https/api/v1/lists/" \
        -H 'Content-Type: application/json' -d '{"title":"smoke"}')"
created=$(compose exec -T api python manage.py shell -c '
import json
from apps.sharing.serializers import ListCreatedSerializer
from apps.sharing.services.legacy import create_list
shared_list, shared_list.owner_token = create_list(title="smoke")
print(json.dumps(ListCreatedSerializer(shared_list).data))' | tail -n 1)
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
check "TRACE is refused" 405 "$(curl_ -o /dev/null -w '%{http_code}' -X TRACE "$https/")"
# The request id nginx gives each request reaches Django, which echoes it (task 9.1).
check "API responses carry nginx's request id" 1 \
    "$(grep -cE '^x-request-id: [0-9a-f]{32}$' <<<"$headers")"
# Production cookies carry the __Host- prefix: Secure, this host only, path / (task 9.1).
session_headers=$(curl_ -sI "$https/api/v2/session/" | tr -d '\r' | tr 'A-Z' 'a-z')
check "the CSRF cookie is a __Host- cookie" 1 \
    "$(grep -cE '^set-cookie: __host-csrftoken=[^;]+;.*path=/;.*secure' <<<"$session_headers")"

page=$(curl_ "$https/l/$code")
check "public list URL serves the app" 1 "$(grep -c '<div id="app"></div>' <<<"$page")"
page_headers=$(curl_ -sI "$https/l/$code" | tr -d '\r' | tr 'A-Z' 'a-z')
check "app page sends HSTS" "strict-transport-security: max-age=31536000; includesubdomains" \
    "$(grep '^strict-transport-security' <<<"$page_headers")"
check "app page never leaks its URL as a referrer" "referrer-policy: no-referrer" \
    "$(grep '^referrer-policy' <<<"$page_headers")"
check "app page sends a CSP" 1 "$(grep -c "^content-security-policy: default-src 'self'" <<<"$page_headers")"
check "app page declares UTF-8" "content-type: text/html; charset=utf-8" \
    "$(grep '^content-type' <<<"$page_headers")"
check "app page isolates its window" "cross-origin-opener-policy: same-origin" \
    "$(grep '^cross-origin-opener-policy' <<<"$page_headers")"
check "app page turns off unused browser features" 1 \
    "$(grep -c '^permissions-policy: camera=(), microphone=()' <<<"$page_headers")"
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

# Media (docs/v2/13-SECURITY.md#media): the api container (non-root) writes the volume and
# nginx serves it read-only, as inert files.
media_path=$(compose exec -T api python manage.py shell -c '
import io
from PIL import Image
from apps.metadata import images
out = io.BytesIO()
Image.new("RGB", (300, 200), (20, 120, 220)).save(out, format="PNG")
print(images.store(images.process(out.getvalue(), images.ICON), images.ICON))' | tail -n 1)
media_headers=$(curl_ -sI "$https/media/$media_path" | tr -d '\r' | tr 'A-Z' 'a-z')
check "media is served by nginx" "http/2 200" "$(head -n 1 <<<"$media_headers" | sed 's/ *$//')"
check "media has an image type" "content-type: image/webp" "$(grep '^content-type' <<<"$media_headers")"
check "media is never sniffed" "x-content-type-options: nosniff" \
    "$(grep '^x-content-type-options' <<<"$media_headers")"
check "media has a sandbox CSP" "content-security-policy: default-src 'none'; sandbox; frame-ancestors 'none'" \
    "$(grep '^content-security-policy' <<<"$media_headers")"
check "media is cached immutably" "cache-control: public, max-age=31536000, immutable" \
    "$(grep '^cache-control' <<<"$media_headers")"
missing_headers=$(curl_ -sI "$https/media/icons/00/missing.webp" | tr -d '\r' | tr 'A-Z' 'a-z')
check "missing media is a 404" 404 "$(awk 'NR==1 {print $2}' <<<"$missing_headers")"
check "a media 404 is not cached" "" "$(grep '^cache-control' <<<"$missing_headers" || true)"
check "media directories are not listed" 403 \
    "$(curl_ -o /dev/null -w '%{http_code}' "$https/media/icons/")"

# Upload routes take bodies up to 3 MB at nginx (Django: 2 MB per file); others don't.
check "a 1 MB upload reaches the API" 404 \
    "$(head -c 1000000 /dev/zero | curl_ -o /dev/null -w '%{http_code}' -X PUT \
        "$https/api/v2/lists/NoSuchList000000/image/" -H 'Content-Type: multipart/form-data; boundary=x' --data-binary @-)"
check "a 1 MB group image upload reaches the API" 404 \
    "$(head -c 1000000 /dev/zero | curl_ -o /dev/null -w '%{http_code}' -X PUT \
        "$https/api/v2/groups/NoSuchGroup00000/image/" -H 'Content-Type: multipart/form-data; boundary=x' --data-binary @-)"
check "an oversized upload is rejected by nginx" 413 \
    "$(head -c 4000000 /dev/zero | curl_ -o /dev/null -w '%{http_code}' -X PUT \
        "$https/api/v2/lists/NoSuchList000000/image/" -H 'Content-Type: multipart/form-data; boundary=x' --data-binary @-)"

# 1 creation was attempted above; the limit is 30/hour per client and is checked before the
# 410. A fresh spoofed X-Forwarded-For on every request must not reset it: nginx overwrites
# the header.
statuses=$(for i in $(seq 30); do
    curl_ -o /dev/null -w '%{http_code}\n' -X POST "$https/api/v1/lists/" \
        -H "X-Forwarded-For: 198.51.100.$i" -H 'Content-Type: application/json' -d '{"title":"t"}'
done | sort | uniq -c | awk '{print $2 "x" $1}' | paste -sd' ')
check "spoofed X-Forwarded-For cannot bypass rate limits" "410x29 429x1" "$statuses"

# `compose port` prints ":0" for a port that is exposed but has no host binding.
published=$(compose port api 8000 2>/dev/null || true)
check "API port is not published" "not published" \
    "$([[ -z "$published" || "$published" == ":0" ]] && echo "not published" || echo "$published")"

# Maintenance mode (task 9.5): while the switch file exists every request gets the static 503
# page, the API's included; removing it restores service without a reload.
touch "$MAINTENANCE_DIR/on"
maintenance_headers=$(curl_ -sI "$https/l/$code" | tr -d '\r' | tr 'A-Z' 'a-z')
check "maintenance mode answers 503" 503 "$(awk 'NR==1 {print $2}' <<<"$maintenance_headers")"
check "maintenance mode asks clients to retry" "retry-after: 600" "$(grep '^retry-after' <<<"$maintenance_headers")"
check "maintenance mode covers the API" 503 "$(curl_ -o /dev/null -w '%{http_code}' "$https/healthz")"
check "maintenance mode serves its page" 1 "$(curl_ "$https/r/x" | grep -c "We'll be right back")"
rm -f "$MAINTENANCE_DIR/on"
check "service returns when maintenance ends" 200 "$(curl_ -o /dev/null -w '%{http_code}' "$https/healthz")"

# nginx looks the API up per request, so a recreated api container (possibly at a new
# address, as after an upgrade) is reached without restarting nginx.
compose up -d --no-deps --force-recreate --wait api >/dev/null 2>&1
check "nginx reaches a recreated API" 200 "$(curl_ -o /dev/null -w '%{http_code}' "$https/healthz")"

# The background worker (docs/v2/adr/ADR-008): every replica becomes healthy, and a task
# queued by the API runs (a test task: the only real one arrives with link metadata, 7.3).
echo "Waiting for the worker..."
for _ in $(seq 45); do
    [[ -n "$(compose ps worker --format '{{.Health}}')" ]] && \
        ! compose ps worker --format '{{.Health}}' | grep -qv '^healthy$' && break
    sleep 2
done
check "every worker replica is healthy" "healthy healthy" \
    "$(compose ps worker --format '{{.Health}}' | sort | paste -sd' ')"
compose exec -T api python manage.py shell -c '
from apps.metadata.tasks import enqueue_on_commit
from apps.metadata.tests.sample_tasks import echo
enqueue_on_commit(echo, "smoke")' >/dev/null
task_state() {
    compose exec -T api python manage.py shell -c '
from django_tasks_db.models import DBTaskResult
r = DBTaskResult.objects.filter(args_kwargs__args=["smoke"]).first()
print(r.status, r.return_value)' | tail -n 1
}
for _ in $(seq 15); do [[ "$(task_state)" == SUCCESSFUL* ]] && break; sleep 2; done
check "the worker runs a task queued by the API" "SUCCESSFUL smoke" "$(task_state)"

echo
if [[ $failures -eq 0 ]]; then echo "All smoke checks passed."; else echo "$failures check(s) failed."; fi
exit "$failures"
