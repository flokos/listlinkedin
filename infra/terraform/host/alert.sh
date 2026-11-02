#!/bin/bash
# Mails standard input to MODERATION_EMAIL through the app's SMTP relay (settings from .env).
# Installed as /usr/local/sbin/lli-alert:   echo "message" | lli-alert "subject"
# The SMTP password reaches curl through a netrc file descriptor, never the command line.
set -euo pipefail
env=/srv/listlinkedin/.env
get() { grep -m1 "^$1=" "$env" | cut -d= -f2-; }
from_header=$(get DEFAULT_FROM_EMAIL)
from=$(sed -E 's/.*<([^>]+)>.*/\1/' <<< "$from_header")
to=$(get MODERATION_EMAIL)
{
  printf 'From: %s\r\nTo: %s\r\nSubject: [listlinkedin] %s\r\nDate: %s\r\n\r\n' \
    "$from_header" "$to" "${1:-alert from $(hostname)}" "$(date -R)"
  cat
} | curl -sS --ssl-reqd --url "smtp://$(get EMAIL_HOST):$(get EMAIL_PORT)" \
  --mail-from "$from" --mail-rcpt "$to" \
  --netrc-file <(printf 'machine %s login %s password %s\n' \
    "$(get EMAIL_HOST)" "$(get EMAIL_HOST_USER)" "$(get EMAIL_HOST_PASSWORD)") \
  -T -
