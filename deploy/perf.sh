#!/usr/bin/env bash
# Measures response times of the production stack against the targets in
# docs/v2/14-INFRASTRUCTURE.md#performance-targets-initial (task 9.2):
#
#   bash deploy/perf.sh            # ports 8081/8444; runs a few minutes
#
# It seeds a 100-link public list, a public group of 30 lists, 100,000 public lists for the
# directory and 20,000 rate-limit entries (a busy day), then times each endpoint through
# nginx: p50 and p95 of single requests, one at a time, over 60 requests after a warm-up.
# It also prints the directory search's query plan. Nothing is kept: the isolated compose
# project is removed on exit. Numbers depend on the machine; record them with its size.
set -euo pipefail
cd "$(dirname "$0")/.."

work=$(mktemp -d)
export COMPOSE_PROJECT_NAME=listlinkedin-perf
export SERVER_NAME=go.example.test
export PUBLIC_BASE_URL="https://$SERVER_NAME" DJANGO_ALLOWED_HOSTS="$SERVER_NAME"
export DJANGO_SECRET_KEY="$(openssl rand -base64 48)"
export POSTGRES_DB=perf POSTGRES_USER=perf POSTGRES_PASSWORD="$(openssl rand -hex 16)"
export TLS_CERT_DIR="$work/certs" ACME_WEBROOT="$work/acme"
export HTTP_PORT="${HTTP_PORT:-8081}" HTTPS_PORT="${HTTPS_PORT:-8444}"
export THROTTLE_DIRECTORY=100000/hour METADATA_FETCH_ENABLED=false WORKER_REPLICAS=1
SAMPLES="${SAMPLES:-60}"

compose() { docker compose -f compose.prod.yaml "$@"; }
cleanup() {
    compose down -v --remove-orphans >/dev/null 2>&1 || true
    rm -rf "$work"
}
trap cleanup EXIT

mkdir -p "$work/certs" "$work/acme"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=$SERVER_NAME" \
    -addext "subjectAltName=DNS:$SERVER_NAME" \
    -keyout "$work/certs/privkey.pem" -out "$work/certs/fullchain.pem" 2>/dev/null
compose up --build -d --quiet-pull >/dev/null 2>&1

https="https://$SERVER_NAME:$HTTPS_PORT"
curl_() {
    curl -sS --resolve "$SERVER_NAME:$HTTPS_PORT:127.0.0.1" --cacert "$work/certs/fullchain.pem" "$@"
}
for _ in $(seq 90); do
    [[ "$(curl_ -o /dev/null -w '%{http_code}' "$https/healthz" 2>/dev/null)" == 200 ]] && break
    sleep 2
done

echo "Seeding (100,000 public lists take a minute)..."
codes=$(compose exec -T api python manage.py shell -c '
import json, logging
logging.disable(logging.INFO)  # the seed itself is not what is measured
from django.db import connection
from django.utils import timezone
from apps.accounts.models import User
from apps.groups import services as groups
from apps.groups.models import GroupList
from apps.sharing.models import SharedList
from apps.sharing.selectors import Principal
from apps.sharing.services import links, lists
from apps.shortener.models import ShortRedirect

owner = User.objects.create_user("perf@example.test", "perf-password-123")
who = Principal(user=owner)
def public_list(title, n):
    shared, _ = lists.create_list(who, title=title, description="Links for measuring")
    for i in range(n):
        links.add_link(who, shared.pk, destination_url=f"https://site{i}.example/{title}")
    SharedList.objects.filter(pk=shared.pk).update(visibility="public")
    return shared
big = public_list("Hundred", 100)
group = groups.create_group(who, title="Thirty")
for i in range(30):
    GroupList.objects.create(group=group, shared_list=public_list(f"Part {i}", 3), position=i)
type(group).objects.filter(pk=group.pk).update(visibility="public")
short = ShortRedirect.objects.filter(link__shared_list=big).values_list("code", flat=True)[0]

words = ["tools", "design", "python", "docker", "reading", "recipes", "travel", "music",
         "finance", "health", "games", "science", "history", "garden", "kids", "jobs"]
with connection.cursor() as cursor:
    cursor.execute(
        """
        INSERT INTO sharing_sharedlist (id, public_code, owner_id, title, description, slug,
            visibility, allow_fork, allow_branch, tags, head_revision, created_at, updated_at)
        SELECT gen_random_uuid(), substr(md5(random()::text || n), 1, 16), %s,
            initcap((%s::text[])[1 + mod(n, 16)] || " " || (%s::text[])[1 + mod(n / 16, 16)]
                || " " || n),
            "A collection about " || (%s::text[])[1 + mod(n / 7, 16)],
            "", "public", false, false,
            ARRAY[(%s::text[])[1 + mod(n, 16)], (%s::text[])[1 + mod(n / 3, 16)]],
            0, now() - (n || " minutes")::interval, now() - (n || " minutes")::interval
        FROM generate_series(1, 100000) AS n
        """.replace(chr(34), chr(39)),
        [owner.pk, words, words, words, words, words],
    )
    cursor.execute(
        """
        INSERT INTO rate_limit_cache (cache_key, value, expires)
        SELECT ":1:throttle_list_manage_10." || (n / 250) || "." || mod(n, 250), "gAWVBQAAAAAAAABdlC4=",
            now() + interval "1 hour"
        FROM generate_series(1, 20000) AS n
        """.replace(chr(34), chr(39))
    )
    cursor.execute("ANALYZE")
print(json.dumps({"list": big.public_code, "group": group.code, "short": short}))
' | tail -n 1)
list=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['list'])" "$codes")
group=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['group'])" "$codes")
short=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['short'])" "$codes")

# time <label> <path>: p50 and p95 in milliseconds over $SAMPLES requests, after 5 warm-ups.
time_() {
    local label=$1 path=$2 times=()
    for _ in 1 2 3 4 5; do curl_ -o /dev/null "$https$path"; done
    for _ in $(seq "$SAMPLES"); do
        times+=("$(curl_ -o /dev/null -w '%{time_total}' "$https$path")")
    done
    printf '%s\n' "${times[@]}" | python3 -c "
import sys
t = sorted(float(x) * 1000 for x in sys.stdin)
p = lambda q: t[min(len(t) - 1, int(q * len(t)))]
print(f'{sys.argv[1]:<34} p50 {p(0.5):6.1f} ms   p95 {p(0.95):6.1f} ms')" "$label"
}

echo
echo "Response times through nginx ($SAMPLES requests each, one at a time):"
time_ "list detail (100 links)" "/api/v2/lists/$list/"
time_ "list links (100 links)" "/api/v2/lists/$list/links/"
time_ "group detail" "/api/v2/groups/$group/"
time_ "group lists (30)" "/api/v2/groups/$group/lists/"
time_ "short URL /r/" "/r/$short"
time_ "directory, newest first" "/api/v2/directory/lists/"
time_ "directory, q=tools" "/api/v2/directory/lists/?q=tools"
time_ "directory, q=pyth (partial)" "/api/v2/directory/lists/?q=pyth"
time_ "directory, q + tag" "/api/v2/directory/lists/?q=garden&tags=kids"
time_ "directory, tags=docker,music" "/api/v2/directory/lists/?tags=docker,music"
time_ "directory groups" "/api/v2/directory/groups/"
time_ "popular tags" "/api/v2/directory/tags/"

echo
echo "Query plan of a directory search (q=tools, best match, first page):"
compose exec -T api python manage.py shell -c '
from django.db import connection
from apps.sharing.selectors import public_lists
qs = public_lists(None, q="tools", tags=[], ordering="-relevance")[:20]
sql, params = qs.query.sql_with_params()
with connection.cursor() as cursor:
    cursor.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql, params)
    for (line,) in cursor.fetchall():
        print("  " + line)
'
