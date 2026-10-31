#!/usr/bin/env bash
# Restarts the production stack's unhealthy containers and raises an alert. Compose marks a
# container unhealthy but never restarts it (docs/v2/14-INFRASTRUCTURE.md#health-checks-and-observability).
# Run it on the host every few minutes, from cron or a systemd timer:
#
#   */2 * * * * cd /srv/listlinkedin && ALERT_COMMAND='mail -s listlinkedin ops@example.com' bash deploy/autoheal.sh
#
# Checks every service of compose.prod.yaml: an `unhealthy` container (the api's /healthz, the
# worker's check_worker, the database's pg_isready) is restarted; one that has stopped is
# reported (restart: unless-stopped brings back crashes, so a stopped one was stopped on
# purpose or keeps failing). Each finding is written to stderr and, when ALERT_COMMAND is
# set, piped to that command as one message on its standard input.
set -euo pipefail
cd "$(dirname "$0")/.."

compose() { docker compose -f compose.prod.yaml "$@"; }
findings=()

while read -r name service state health; do
    if [[ $service == migrate ]]; then
        continue  # runs once at start-up and exits
    elif [[ $health == unhealthy ]]; then
        docker restart "$name" > /dev/null
        findings+=("$name ($service) was unhealthy and has been restarted.")
    elif [[ $state != running ]]; then
        findings+=("$name ($service) is $state.")
    fi
done < <(compose ps --all --format '{{.Name}} {{.Service}} {{.State}} {{if .Health}}{{.Health}}{{else}}-{{end}}')

if (( ${#findings[@]} )); then
    message=$(printf 'listlinkedin on %s at %s UTC:\n' "$(hostname)" "$(date -u '+%F %T')"
        printf -- '- %s\n' "${findings[@]}"
        printf 'Logs: docker compose -f compose.prod.yaml logs --since 30m <service>\n')
    echo "$message" >&2
    if [[ -n ${ALERT_COMMAND:-} ]]; then
        echo "$message" | sh -c "$ALERT_COMMAND"
    fi
    exit 1
fi
