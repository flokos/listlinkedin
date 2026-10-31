#!/usr/bin/env bash
# shellcheck disable=SC2016  # $POSTGRES_* are meant to expand inside the db container
# Backs up the production stack: the database (`pg_dump -Fc`) and the uploaded images (the
# `media` volume, as a tar). Run it on the host, from a daily cron job or systemd timer:
#
#   bash deploy/backup.sh                    # into /var/backups/listlinkedin
#   bash deploy/backup.sh /mnt/backups       # or another directory
#
# Writes db-<UTC time>.dump and media-<UTC time>.tar, checks that the dump can be read, and
# deletes backups older than BACKUP_KEEP_DAYS (default 14). Copy the directory off the host
# too: a backup on the same disk doesn't survive losing that disk. Restore with
# deploy/restore.sh, and test a restore monthly (docs/deployment.md#backups).
set -euo pipefail
cd "$(dirname "$0")/.."

dir=${1:-${BACKUP_DIR:-/var/backups/listlinkedin}}
keep_days=${BACKUP_KEEP_DAYS:-14}
compose() { docker compose -f compose.prod.yaml "$@"; }

stamp=$(date -u +%Y%m%dT%H%M%SZ)
umask 077  # the dump holds account data
mkdir -p "$dir"
db="$dir/db-$stamp.dump" media="$dir/media-$stamp.tar"

# A consistent snapshot while the site stays up. Written under a temporary name first, so a
# failed run never leaves a file that looks like a good backup.
compose exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > "$db.part"
compose exec -T db pg_restore --list < "$db.part" > /dev/null
mv "$db.part" "$db"

# Image files are never changed once written, so a copy taken while the site runs is complete
# for every row in the dump, apart from images uploaded during these few seconds.
compose exec -T api tar -C /srv/media -cf - . > "$media.part"
mv "$media.part" "$media"

find "$dir" -maxdepth 1 \( -name 'db-*.dump' -o -name 'media-*.tar' \) -mtime "+$keep_days" -delete
echo "Backed up to $db ($(du -h "$db" | cut -f1)) and $media ($(du -h "$media" | cut -f1))."
