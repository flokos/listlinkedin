#!/bin/bash
# Containers may not open connections to private, link-local (cloud metadata) or CGNAT
# addresses outside the host: defence in depth for the worker's SSRF-safe fetcher
# (docs/v2/14-INFRASTRUCTURE.md#worker-egress). Traffic between containers on a compose
# bridge (`-o br-+`) is never matched, so the api and worker still reach db.
set -euo pipefail
ranges=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,100.64.0.0/10
for in_if in br-+ docker0; do
  rule=(DOCKER-USER -i "$in_if" ! -o br-+ -d "$ranges" -m conntrack --ctstate NEW -j DROP)
  iptables -C "${rule[@]}" 2>/dev/null || iptables -I "${rule[@]}"
done
