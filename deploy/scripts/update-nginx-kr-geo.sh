#!/bin/bash
set -euo pipefail
# 대한민국(KR) CIDR — https://www.ipdeny.com/ipblocks/ (aggregated)
V4_URL="https://www.ipdeny.com/ipblocks/data/aggregated/kr-aggregated.zone"
V6_URL="https://www.ipdeny.com/ipv6/ipaddresses/aggregated/kr-aggregated.zone"
OUT="/etc/nginx/snippets/kr-geo-kr-cidr.conf"
TMP="$(mktemp)"

{
  echo "# Generated $(date -u +%Y-%m-%dT%H:%M:%SZ) from ipdeny.com (KR)"
  curl -fsSL "$V4_URL" | sed '/^[[:space:]]*$/d; /^#/d' | while read -r cidr; do
    [ -n "$cidr" ] && printf '%s 1;\n' "$cidr"
  done
  curl -fsSL "$V6_URL" | sed '/^[[:space:]]*$/d; /^#/d' | while read -r cidr; do
    [ -n "$cidr" ] && printf '%s 1;\n' "$cidr"
  done
} > "$TMP"

install -m 644 -o root -g root "$TMP" "$OUT"
rm -f "$TMP"
nginx -t
systemctl reload nginx
echo "KR geo CIDR updated: $(wc -l < "$OUT") lines"
