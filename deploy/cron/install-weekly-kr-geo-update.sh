#!/bin/bash
# Weekly refresh of Korea CIDR lists (run once: sudo bash deploy/cron/install-weekly-kr-geo-update.sh)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
install -m 755 "$ROOT/deploy/scripts/update-nginx-kr-geo.sh" /usr/local/sbin/update-nginx-kr-geo.sh
ln -sf /usr/local/sbin/update-nginx-kr-geo.sh /etc/cron.weekly/update-nginx-kr-geo
