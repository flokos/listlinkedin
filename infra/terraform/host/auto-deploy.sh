#!/bin/bash
# Pull-based continuous deployment (ADR-018). Deploys the latest GitHub Release when it is
# newer than the version running, following docs/deployment.md "Upgrades": build while the
# old version serves, back up, `up --wait`, check health. On failure it puts the previous
# images back, restores the backup if migrations may have run, and mails MODERATION_EMAIL
# (lli-alert) either way. Run every 5 minutes by listlinkedin-deploy.timer.
#
#   sudo lli-auto-deploy           # deploy the latest release if it is new
#   sudo lli-auto-deploy v2.1.0    # deploy this tag now (retries a failed one, skips the checks
#                                  # for older releases and [manual-deploy])
set -euo pipefail

app=/srv/listlinkedin
repo=${DEPLOY_REPO:-flokos/listlinkedin}
state=/var/lib/listlinkedin
backups=/var/backups/listlinkedin
images=(listlinkedin listlinkedin-nginx)

mkdir -p "$state"
exec 9>/run/lock/listlinkedin-deploy.lock
flock -n 9 || { echo "another deploy is running"; exit 0; }
cd "$app"

g() { runuser -u ubuntu -- git "$@"; }   # the checkout belongs to ubuntu
compose() { docker compose -f compose.prod.yaml "$@"; }
log() { echo "$(date -u +%FT%TZ) $*"; }
alert() { lli-alert "$1" || log "alert mail failed"; }
host=$(grep -m1 '^SERVER_NAME=' .env | cut -d= -f2-)
healthy() { curl -fsS --max-time 10 --resolve "$host:443:127.0.0.1" "https://$host/healthz" | grep -q '"ok"'; }

# Skip a tag for good (until deployed by hand), alerting once.
skip() {
  log "$1"
  echo "$tag" > "$state/failed-tag"
  echo "$1" | alert "release $tag not deployed"
  exit 0
}

forced=${1:-}
if [ -n "$forced" ]; then
  tag=$forced
  notes=""
else
  release=$(curl -fsS --max-time 20 -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$repo/releases/latest")
  tag=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])' <<< "$release")
  notes=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("body") or "")' <<< "$release")
fi
[[ $tag =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { log "ignoring release tag '$tag'"; exit 1; }

deployed=$(cat "$state/deployed-tag" 2>/dev/null || true)
failed=$(cat "$state/failed-tag" 2>/dev/null || true)
if [ -z "$forced" ]; then
  [ "$tag" = "$deployed" ] && exit 0
  [ "$tag" = "$failed" ] && exit 0   # alerted once; retry with: sudo lli-auto-deploy <tag>
fi

g fetch --quiet --force --tags origin '+refs/heads/main:refs/remotes/origin/main'
prev=$(g rev-parse HEAD)
target=$(g rev-parse "refs/tags/$tag^{commit}")

g merge-base --is-ancestor "$target" origin/main || skip "$tag is not on main; releases are tags on main."
if [ -z "$forced" ]; then
  if [ "$target" = "$prev" ]; then
    echo "$tag" > "$state/deployed-tag"
    log "$tag is the commit already running; recorded it as deployed"
    exit 0
  fi
  g merge-base --is-ancestor "$prev" "$target" ||
    skip "$tag does not contain the running version ($(g describe --tags --always "$prev")): refusing to go back automatically."
  if grep -qiF '[manual-deploy]' <<< "$notes"; then
    skip "The release notes of $tag ask for a manual deploy (docs/deployment.md#upgrades). Deploy it by hand, or run: sudo lli-auto-deploy $tag"
  fi
fi

logfile="$state/deploy-$tag.log"
exec > >(tee -a "$logfile") 2>&1
log "deploying $tag over $(g describe --tags --always "$prev")"

for img in "${images[@]}"; do docker image tag "$img:prod" "$img:rollback"; done
db="" media=""

# Roll back to the previous checkout and images. $1: the step that failed.
fail() {
  log "FAILED at $1; rolling back"
  g checkout --quiet --detach "$prev"
  for img in "${images[@]}"; do docker image tag "$img:rollback" "$img:prod"; done
  if [ -n "$db" ]; then
    bash deploy/restore.sh --yes "$db" "$media" || log "restore failed"
  fi
  echo "$tag" > "$state/failed-tag"
  {
    echo "Deploying $tag failed at: $1."
    echo "Rolled back to $(g describe --tags --always "$prev")$([ -n "$db" ] && echo ", database restored from $db")."
    echo "Health now: $(healthy && echo ok || echo FAILING)"
    echo "Retry after a fix: sudo lli-auto-deploy $tag"
    echo
    tail -n 80 "$logfile"
  } | alert "deploy of $tag FAILED"
  exit 1
}

g checkout --quiet --detach "$target"
compose build --pull || fail "build"
bash deploy/backup.sh "$backups" || fail "backup"
db=$(ls -t "$backups"/db-*.dump | head -n 1)
media=$(ls -t "$backups"/media-*.tar | head -n 1)
compose up -d --wait --wait-timeout 600 || fail "start (see: docker compose -f compose.prod.yaml logs migrate api)"
for _ in $(seq 1 12); do healthy && break; sleep 5; done
healthy || fail "health check"

echo "$tag" > "$state/deployed-tag"
rm -f "$state/failed-tag"
docker image prune -f > /dev/null
log "deployed $tag"
{
  echo "$tag is live on https://$host/ (was $(g describe --tags --always "$prev"))."
  echo "Backup taken before the upgrade: $db"
  echo
  compose ps --format 'table {{.Service}}\t{{.Status}}'
} | alert "deployed $tag"
