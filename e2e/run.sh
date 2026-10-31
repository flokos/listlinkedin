#!/usr/bin/env bash
# End-to-end browser tests against the production stack (nginx + built Vue app + Gunicorn
# + PostgreSQL) over HTTPS, in Chromium, Firefox and WebKit. Docker only; runs locally and
# in CI. Arguments go to `playwright test`:
#
#   bash e2e/run.sh                         # everything
#   bash e2e/run.sh --project=webkit -g share
#
# The HTML report (with traces of failures) is written to e2e/report/. Everything the
# script starts is removed on exit.
set -euo pipefail
cd "$(dirname "$0")/.."

work=$(mktemp -d)
export COMPOSE_PROJECT_NAME=listlinkedin-e2e
export SERVER_NAME=go.example.test
export PUBLIC_BASE_URL="https://$SERVER_NAME" DJANGO_ALLOWED_HOSTS="$SERVER_NAME"
export DJANGO_SECRET_KEY="$(openssl rand -base64 48)"
export POSTGRES_DB=e2e POSTGRES_USER=e2e POSTGRES_PASSWORD="$(openssl rand -hex 16)"
export TLS_CERT_DIR="$work/certs" ACME_WEBROOT="$work/acme"
# Random free host ports: the browsers reach nginx over the compose network, not the host.
export HTTP_PORT=0 HTTPS_PORT=0
# Every browser shares one client IP; the default 30 lists/hour would throttle the suite.
# The rate-limit UI is tested with mocked responses instead.
export THROTTLE_LIST_CREATE=10000/hour THROTTLE_LIST_MANAGE=100000/hour
export THROTTLE_GROUP_CREATE=10000/hour THROTTLE_GROUP_MANAGE=100000/hour
export THROTTLE_DIRECTORY=100000/hour  # Explore: searches as you type, from every browser
export THROTTLE_REPORT=10000/hour  # reports, from every browser

# The production stack plus Mailpit for account emails (e2e/compose.e2e.yaml).
compose() { docker compose -f compose.prod.yaml -f e2e/compose.e2e.yaml "$@"; }
status=1
cleanup() {
    if [[ $status -ne 0 ]]; then compose logs --no-color --tail=40 api nginx || true; fi
    compose down -v --remove-orphans >/dev/null 2>&1 || true
    rm -rf "$work"
}
trap cleanup EXIT

mkdir -p "$work/certs" "$work/acme"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=$SERVER_NAME" \
    -addext "subjectAltName=DNS:$SERVER_NAME" \
    -keyout "$work/certs/privkey.pem" -out "$work/certs/fullchain.pem" 2>/dev/null

echo "Building and starting the production stack..."
compose up --build -d --quiet-pull 2>&1 | grep -iE "error|fail" || true
docker build -q -t listlinkedin-e2e e2e >/dev/null

nginx_ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' \
    "$(compose ps -q nginx)")
network="${COMPOSE_PROJECT_NAME}_default"

e2e() {
    docker run --rm --network "$network" --add-host "$SERVER_NAME:$nginx_ip" \
        --ipc=host -e CI -e E2E_RETRIES -e E2E_WORKERS "$@"
}

echo "Waiting for the app..."
for _ in $(seq 60); do
    e2e --entrypoint curl listlinkedin-e2e -skf -o /dev/null "https://$SERVER_NAME/healthz" && break
    sleep 2
done

rm -rf e2e/report e2e/test-results
set +e
e2e -v "$PWD/e2e/report:/e2e/report" -v "$PWD/e2e/test-results:/e2e/test-results" \
    listlinkedin-e2e "$@"
status=$?
set -e
echo
echo "Report: e2e/report/index.html"
exit "$status"
