#!/usr/bin/env bash
# shellcheck disable=SC2016  # $POSTGRES_* are meant to expand inside the db container
# Restores a backup made by deploy/backup.sh into the production stack, replacing the
# database and the uploaded images. Run it on the host:
#
#   bash deploy/restore.sh --yes /var/backups/listlinkedin/db-….dump /var/backups/listlinkedin/media-….tar
#
# It stops the services that use the database, replaces the database and the `media` volume,
# applies migrations (a backup from an older release is brought up to date), then starts the
# stack again. Everything written since the backup is lost, so it asks for --yes.
#
# Monthly restore test, without touching production: restore into a separate compose project
# on other ports, check it, and remove it (docs/deployment.md#backups):
#
#   COMPOSE_PROJECT_NAME=listlinkedin-restore-test HTTP_PORT=8080 HTTPS_PORT=8443 \
#     bash deploy/restore.sh --yes db-….dump media-….tar
#   docker compose -p listlinkedin-restore-test -f compose.prod.yaml down -v
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ${1:-} != --yes || $# -ne 3 ]]; then
    echo "usage: $0 --yes <db-….dump> <media-….tar>  (replaces the database and media)" >&2
    exit 2
fi
db=$2 media=$3
[[ -r $db && -r $media ]] || { echo "Can't read $db or $media" >&2; exit 2; }
compose() { docker compose -f compose.prod.yaml "$@"; }

compose stop nginx api worker cleanup
compose up -d --wait db
compose exec -T db pg_restore --list < "$db" > /dev/null  # a readable dump, before dropping

echo "Replacing the database..."
compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists --force "$POSTGRES_DB" &&
    createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --exit-on-error' < "$db"

echo "Replacing the uploaded images..."
compose run --rm --no-deps -T api sh -c \
    'find /srv/media -mindepth 1 -delete && tar -C /srv/media -xf -' < "$media"

# Starting the stack runs `migrate` first; the other services wait for it.
compose up -d
echo "Restored. Check it: curl https://\$SERVER_NAME/healthz, then sign in and open a list."
