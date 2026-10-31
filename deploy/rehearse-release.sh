#!/usr/bin/env bash
# shellcheck disable=SC2016  # $POSTGRES_* are meant to expand inside the db container
# Rehearses the V1 → V2 release on this machine with the runbook's own commands
# (docs/v2/06-MIGRATION-PLAN.md#runbook), in an isolated compose project, and prints the
# timings for docs/v2/22-RELEASE-REHEARSAL.md. Docker only; everything it starts is removed
# on exit.
#
#   bash deploy/rehearse-release.sh                  # V1 data seeded through V1 itself
#   bash deploy/rehearse-release.sh v1-prod.dump     # a copy of production (pg_dump -Fc)
#
# V1 (V1_REF, default v1.0.0) and V2 (V2_REF, default v2.0.0, the last release with the
# legacy path: v2.1.0 retired it) each run from a git worktree.
#
# 1. V1 runs with the dump restored, or
#    else seeded: lists created through V1's API (edit links included), then SEED_LISTS more
#    (default 20000, 10 links each, 1% expired) in SQL.
# 2. The cutover, in place as on the server: V2's nginx takes over with the maintenance page,
#    V1 stops, the database is dumped, V2 migrates (timed, per migration) and starts, the page
#    ends. Then checks: nothing lost, legacy lists unlisted and expiring as before, baseline
#    revisions, short URLs, the V1 API, an edit link, claiming, the worker, the backfill.
# 3. The rollback, in place: the pre-cutover dump goes back and V1's images run again.
#
# A production dump holds personal data: run this only where production data may be.
set -euo pipefail
cd "$(dirname "$0")/.."

dump=${1:-}
[[ -z $dump ]] || dump=$(realpath "$dump")
v1_ref=${V1_REF:-v1.0.0}
v2_ref=${V2_REF:-v2.0.0}
seed_lists=${SEED_LISTS:-20000}
work=$(mktemp -d)
report="$work/report.txt"

export SERVER_NAME=go.example.test
export PUBLIC_BASE_URL="https://$SERVER_NAME" DJANGO_ALLOWED_HOSTS="$SERVER_NAME"
export DJANGO_SECRET_KEY="$(openssl rand -base64 48)"
export POSTGRES_DB=listlinkedin POSTGRES_USER=listlinkedin POSTGRES_PASSWORD="$(openssl rand -hex 16)"
export TLS_CERT_DIR="$work/certs" ACME_WEBROOT="$work/acme" MAINTENANCE_DIR="$work/maintenance"
export HTTP_PORT=0 HTTPS_PORT=0
export THROTTLE_LIST_CREATE=100000/hour THROTTLE_LIST_MANAGE=100000/hour

# One project, as on the server: V1's and V2's compose files manage the same containers.
v1() { docker compose -p listlinkedin-rehearsal -f "$work/v1/compose.prod.yaml" -f "$work/v1-images.yaml" "$@"; }
v2() { docker compose -p listlinkedin-rehearsal -f "$work/v2/compose.prod.yaml" "$@"; }
psql_() { local stack=$1; shift; "$stack" exec -T db psql -qAtX -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 "$@"; }

status=1
cleanup() {
    if [[ $status -ne 0 ]]; then v2 logs --no-color --tail=30 migrate api 2>/dev/null || true; fi
    for stack in v2 v1; do "$stack" down -v --remove-orphans >/dev/null 2>&1 || true; done
    docker rmi listlinkedin-rehearsal-v1:prod listlinkedin-rehearsal-v1-nginx:prod >/dev/null 2>&1 || true
    git worktree remove --force "$work/v1" >/dev/null 2>&1 || true
    git worktree remove --force "$work/v2" >/dev/null 2>&1 || true
    rm -rf "$work"
}
trap cleanup EXIT

now() { date +%s.%N; }
since() { awk -v a="$1" -v b="$(now)" 'BEGIN { printf "%.1f s", b - a }'; }
say() { echo "$*" | tee -a "$report"; }
failures=0
check() {  # check <description> <expected> <actual>
    if [[ "$3" == "$2" ]]; then say "ok    $1"; else
        say "FAIL  $1: expected '$2', got '$3'"; failures=$((failures + 1))
    fi
}
https_of() { echo "https://$SERVER_NAME:$("$1" port nginx 443 | sed 's/.*://')"; }
curl_() {  # curl_ <stack> <curl args…>; the URL's {} is replaced by the stack's base URL
    local stack=$1 base port; shift
    base=$(https_of "$stack"); port=${base##*:}
    curl -sS --resolve "$SERVER_NAME:$port:127.0.0.1" --cacert "$work/certs/fullchain.pem" \
        "${@//\{\}/$base}"
}

mkdir -p "$work/certs" "$work/acme" "$work/maintenance"
cp deploy/maintenance/maintenance.html "$work/maintenance/"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=$SERVER_NAME" \
    -addext "subjectAltName=DNS:$SERVER_NAME" \
    -keyout "$work/certs/privkey.pem" -out "$work/certs/fullchain.pem" 2>/dev/null

say "Release rehearsal, $(date -u '+%F %T') UTC, V1 $(git rev-parse --short "$v1_ref^{commit}"), V2 $(git rev-parse --short "$v2_ref^{commit}")"
git worktree add --detach "$work/v1" "$v1_ref" >/dev/null 2>&1
git worktree add --detach "$work/v2" "$v2_ref" >/dev/null 2>&1
# V1 and V2 build the same image names; give V1's its own for the rehearsal.
cat > "$work/v1-images.yaml" <<'EOF'
services:
  migrate: { image: "listlinkedin-rehearsal-v1:prod" }
  api: { image: "listlinkedin-rehearsal-v1:prod" }
  cleanup: { image: "listlinkedin-rehearsal-v1:prod" }
  nginx: { image: "listlinkedin-rehearsal-v1-nginx:prod" }
EOF
echo "Building V1 and V2 images..."
v1 build -q >/dev/null
v2 build -q >/dev/null

# --- 1. V1 and its data -------------------------------------------------------------------
token=$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '=')
echo "Starting V1..."
v1 up -d --wait >/dev/null 2>&1
if [[ -z $dump ]]; then
    created=$(curl_ v1 -X POST "{}/api/v1/lists/" -H 'Content-Type: application/json' \
        -d '{"title":"Friday team bonding"}')
    code=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["public_code"])' <<<"$created")
    token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["owner_token"])' <<<"$created")
    for n in 1 2 3; do
        curl_ v1 -o /dev/null -X POST "{}/api/v1/lists/$code/links/" \
            -H "Authorization: Bearer $token" -H 'Content-Type: application/json' \
            -d "{\"destination_url\":\"https://example.com/team/$n\",\"title\":\"Idea $n\"}"
    done
    t=$(now)
    psql_ v1 <<SQL
INSERT INTO sharing_sharedlist (id, public_code, owner_token_hash, title, created_at, updated_at, expires_at)
SELECT gen_random_uuid(), substr(md5('list' || n), 1, 16), md5('a' || n) || md5('b' || n),
       'Seeded list ' || n, c, c, c + interval '30 days'
FROM generate_series(1, $seed_lists) n,
     LATERAL (SELECT now() - CASE WHEN n % 100 = 0 THEN interval '31 days'
                                  ELSE (n % 29) * interval '1 day' END AS c) t;
INSERT INTO sharing_sharedlink (id, shared_list_id, destination_url, title, created_at, updated_at)
SELECT gen_random_uuid(), l.id, 'https://example.com/' || l.public_code || '/' || k,
       CASE WHEN k % 3 = 0 THEN NULL ELSE 'Link ' || k END,
       l.created_at + k * interval '1 minute', l.created_at + k * interval '1 minute'
FROM sharing_sharedlist l, generate_series(1, 10) k WHERE l.title LIKE 'Seeded list %';
INSERT INTO shortener_shortredirect (id, code, link_id, is_active, created_at)
SELECT gen_random_uuid(), substr(md5('link' || l.id::text), 1, 16), l.id, true, l.created_at
FROM sharing_sharedlink l WHERE l.title IS DISTINCT FROM 'Idea 1' AND l.title IS DISTINCT FROM 'Idea 2'
  AND l.title IS DISTINCT FROM 'Idea 3';
ANALYZE;
SQL
    say "V1 seeded: 1 list through the API, $seed_lists in SQL ($(since "$t"))"
    say "  $(psql_ v1 -c "SELECT count(*) || ' lists, ' || (SELECT count(*) FROM sharing_sharedlink) || ' links, '
        || (SELECT count(*) FROM shortener_shortredirect) || ' short URLs, '
        || pg_size_pretty(pg_database_size(current_database())) FROM sharing_sharedlist")"
else
    code=""
    v1 stop api cleanup >/dev/null 2>&1
    t=$(now)
    v1 exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --force "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
    v1 exec -T db pg_restore --no-owner --no-acl --exit-on-error -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$dump"
    say "Production dump restored into V1: $(since "$t")"
    v1 up -d --wait >/dev/null 2>&1
fi

# --- 2. The cutover (runbook steps 6-9) ---------------------------------------------------
fingerprint="SELECT count(*) || '/' || md5(string_agg(id::text || public_code || coalesce(expires_at::text, '-'), ',' ORDER BY id)) FROM sharing_sharedlist"
before_lists=$(psql_ v2 -c "$fingerprint")
before_links=$(psql_ v2 -c "SELECT count(*) || '/' || md5(string_agg(id::text || destination_url, ',' ORDER BY id)) FROM sharing_sharedlink")
before_redirects=$(psql_ v2 -c "SELECT count(*) || '/' || md5(string_agg(code || link_id::text, ',' ORDER BY code)) FROM shortener_shortredirect")
if [[ -z $code ]]; then
    code=$(psql_ v2 -c "SELECT public_code FROM sharing_sharedlist l WHERE expires_at > now() + interval '1 day'
        AND EXISTS (SELECT 1 FROM shortener_shortredirect r JOIN sharing_sharedlink k ON k.id = r.link_id
                    WHERE k.shared_list_id = l.id) ORDER BY created_at DESC LIMIT 1")
fi

echo "Cutover..."
window=$(now)
touch "$MAINTENANCE_DIR/on"
v2 up -d --no-deps nginx >/dev/null 2>&1
check "V2's nginx shows the maintenance page while V1 still runs" 503 \
    "$(curl_ v2 -o /dev/null -w '%{http_code}' "{}/")"
v2 stop api cleanup >/dev/null 2>&1
t=$(now)
v2 exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > "$work/pre-v2.dump"
v2 exec -T db pg_restore --list < "$work/pre-v2.dump" > /dev/null
say "Pre-cutover pg_dump -Fc, checked: $(since "$t"), $(du -h "$work/pre-v2.dump" | cut -f1)"
t=$(now)
v2 run --rm --no-deps -T migrate python manage.py migrate --noinput -v 2 > "$work/migrate.log"
say "V2 migrate on V1 data: $(since "$t") in all; slowest migrations:"
grep -E '^\s+Applying .* OK \(' "$work/migrate.log" | sed -E 's/^\s+Applying (.*)\.\.\. OK \((.*)s\)$/\2 \1/' \
    | sort -rn | head -6 | awk '{ printf "  %7.3f s  %s\n", $1, $2 }' | tee -a "$report"
t=$(now)
v2 up -d --wait >/dev/null 2>&1
say "V2 started, every service healthy: $(since "$t")"
check "the maintenance page stays up until it is ended" 503 "$(curl_ v2 -o /dev/null -w '%{http_code}' "{}/healthz")"
rm -f "$MAINTENANCE_DIR/on"
say "Maintenance window (page on to page off): $(since "$window")"
check "V2 answers once the page is off" 200 "$(curl_ v2 -o /dev/null -w '%{http_code}' "{}/healthz")"

check "every list kept (ids, codes, expiry)" "$before_lists" "$(psql_ v2 -c "$fingerprint")"
check "every link kept" "$before_links" "$(psql_ v2 -c "SELECT count(*) || '/' || md5(string_agg(id::text || destination_url, ',' ORDER BY id)) FROM sharing_sharedlink")"
check "every short URL kept" "$before_redirects" "$(psql_ v2 -c "SELECT count(*) || '/' || md5(string_agg(code || link_id::text, ',' ORDER BY code)) FROM shortener_shortredirect")"
check "legacy lists are unlisted, ownerless, keep their token" 0 \
    "$(psql_ v2 -c "SELECT count(*) FROM sharing_sharedlist WHERE visibility <> 'unlisted' OR owner_id IS NOT NULL OR owner_token_hash IS NULL")"
check "every list has one baseline revision at head 1" "0 0" \
    "$(psql_ v2 -c "SELECT (SELECT count(*) FROM sharing_sharedlist WHERE head_revision <> 1) || ' ' ||
        (SELECT count(*) FROM sharing_sharedlist l WHERE (SELECT count(*) FROM versioning_listrevision r
         WHERE r.shared_list_id = l.id AND r.number = 1 AND r.kind = 'migrated') <> 1)")"
check "baseline snapshots hold every link" 0 \
    "$(psql_ v2 -c "SELECT count(*) FROM sharing_sharedlist l JOIN versioning_listrevision r ON r.shared_list_id = l.id
        WHERE jsonb_array_length(r.snapshot -> 'links') <> (SELECT count(*) FROM sharing_sharedlink k WHERE k.shared_list_id = l.id)")"
check "link positions are 0..n-1, newest first" 0 \
    "$(psql_ v2 -c "SELECT count(*) FROM (SELECT position, row_number() OVER (PARTITION BY shared_list_id
        ORDER BY created_at DESC, id DESC) - 1 AS expected FROM sharing_sharedlink) p WHERE position IS DISTINCT FROM expected")"

short=$(psql_ v2 -c "SELECT r.code || ' ' || k.destination_url FROM shortener_shortredirect r
    JOIN sharing_sharedlink k ON k.id = r.link_id JOIN sharing_sharedlist l ON l.id = k.shared_list_id
    WHERE l.public_code = '$code' LIMIT 1")
check "a short URL redirects to its destination" "302 ${short#* }" \
    "$(curl_ v2 -o /dev/null -w '%{http_code} %{redirect_url}' "{}/r/${short%% *}")"
expired=$(psql_ v2 -c "SELECT r.code FROM shortener_shortredirect r JOIN sharing_sharedlink k ON k.id = r.link_id
    JOIN sharing_sharedlist l ON l.id = k.shared_list_id WHERE l.expires_at < now() LIMIT 1")
if [[ -n $expired ]]; then
    check "an expired list's short URL answers 410" 410 "$(curl_ v2 -o /dev/null -w '%{http_code}' "{}/r/$expired")"
fi
check "the list's page loads" 200 "$(curl_ v2 -o /dev/null -w '%{http_code}' "{}/l/$code")"
check "anyone with the address reads it (v2)" "200 unlisted" \
    "$(curl_ v2 -w ' %{http_code}' "{}/api/v2/lists/$code/" | python3 -c 'import json,sys; b, s = sys.stdin.read().rsplit(" ", 1); print(s, json.loads(b)["visibility"])')"
check "the V1 API still reads it" 200 "$(curl_ v2 -o /dev/null -w '%{http_code}' "{}/api/v1/lists/$code/")"

# An edit link: with a seeded list its real token; with a production dump one list gets a
# known token here, on this copy only.
if [[ -z ${created:-} ]]; then
    psql_ v2 -c "UPDATE sharing_sharedlist SET owner_token_hash = encode(sha256(convert_to('$token', 'UTF8')), 'hex') WHERE public_code = '$code'"
fi
check "an edit link still edits its list" 200 \
    "$(curl_ v2 -o /dev/null -w '%{http_code}' -X PATCH "{}/api/v1/lists/$code/" -H "Authorization: Bearer $token" \
        -H 'Content-Type: application/json' -d '{"title":"Edited after the move"}')"
check "the edit wrote revision 2" "2 edited" \
    "$(psql_ v2 -c "SELECT number || ' ' || kind FROM versioning_listrevision r JOIN sharing_sharedlist l ON l.id = r.shared_list_id
        WHERE l.public_code = '$code' ORDER BY number DESC LIMIT 1")"

# Claiming: a verified account signs in through allauth and claims the list with its token.
v2 exec -T api python manage.py shell -c '
from allauth.account.models import EmailAddress
from apps.accounts.models import User
user = User.objects.create_user("rehearsal@example.test", "rehearsal-password-1")
EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)' >/dev/null 2>&1
jar="$work/cookies"
csrf() { awk '$6 == "__Host-csrftoken" { print $7 }' "$jar"; }
curl_ v2 -o /dev/null -c "$jar" "{}/api/v2/session/"
# nginx passes the host without the port, so the origin Django expects has none either.
base="https://$SERVER_NAME"
check "a V2 account signs in" 200 \
    "$(curl_ v2 -o /dev/null -w '%{http_code}' -b "$jar" -c "$jar" -X POST "{}/_allauth/browser/v1/auth/login" \
        -H "X-CSRFToken: $(csrf)" -H "Origin: $base" -H "Referer: $base/" -H 'Content-Type: application/json' \
        -d '{"email":"rehearsal@example.test","password":"rehearsal-password-1"}')"
check "it claims the legacy list with the edit link" 200 \
    "$(curl_ v2 -o /dev/null -w '%{http_code}' -b "$jar" -c "$jar" -X POST "{}/api/v2/lists/$code/claim/" \
        -H "Authorization: Bearer $token" -H "X-CSRFToken: $(csrf)" -H "Origin: $base" -H "Referer: $base/")"
check "the token stops working after the claim" 403 \
    "$(curl_ v2 -o /dev/null -w '%{http_code}' -X PATCH "{}/api/v1/lists/$code/" -H "Authorization: Bearer $token" \
        -H 'Content-Type: application/json' -d '{"title":"Too late"}')"

check "every worker replica is healthy" "healthy healthy" "$(v2 ps worker --format '{{.Health}}' | sort | paste -sd' ')"
t=$(now)
say "backfill_metadata --dry-run: $(v2 exec -T api python manage.py backfill_metadata --dry-run --limit 10000000 2>/dev/null | tail -n 1) ($(since "$t"))"
t=$(now)
v2 exec -T cleanup python manage.py cleanup_expired >/dev/null 2>&1
say "cleanup_expired on V2 (purges the expired lists): $(since "$t")"

# --- 3. The rollback (runbook "Returning to V1") ------------------------------------------
echo "Rollback..."
t=$(now)
touch "$MAINTENANCE_DIR/on"
v2 stop api worker cleanup >/dev/null 2>&1
v2 exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --force "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
v2 exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --exit-on-error' < "$work/pre-v2.dump"
if ! v1 up -d --no-build --remove-orphans --wait > "$work/rollback-up.log" 2>&1; then
    say "note: V1's start-up reported: $(grep -iE 'error|unhealthy|dependency' "$work/rollback-up.log" | tail -n 2)"
fi
say "Rollback to V1 (page on, restore, V1 started): $(since "$t")"
check "V1 serves the list again" 200 "$(curl_ v1 -o /dev/null -w '%{http_code}' "{}/api/v1/lists/$code/")"
check "V1 short URLs redirect again" "302 ${short#* }" \
    "$(curl_ v1 -o /dev/null -w '%{http_code} %{redirect_url}' "{}/r/${short%% *}")"
check "V1 has every list, as before the cutover" "$before_lists" "$(psql_ v1 -c "$fingerprint")"
check "V2's writes are gone (the edit, the claim)" "0" \
    "$(psql_ v1 -c "SELECT count(*) FROM sharing_sharedlist WHERE title = 'Edited after the move'")"
check "V2's worker is removed" "" "$(docker ps -q --filter label=com.docker.compose.project=listlinkedin-rehearsal \
    --filter label=com.docker.compose.service=worker)"

echo
if [[ $failures -eq 0 ]]; then say "Rehearsal passed."; else say "$failures check(s) failed."; fi
status=$failures
exit "$status"
