#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
sudo systemctl disable --now cloudflared 2>/dev/null || true
sudo cp "$ROOT/deploy/cloudflared/cloudflared-quick.service" /etc/systemd/system/cloudflared-quick.service
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared-quick
sleep 3
echo "발급된 주소 (서비스 재시작 시 바뀔 수 있음):"
sudo journalctl -u cloudflared-quick --no-pager -n 30 | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1 || true
echo ""
echo "수동 확인: sudo journalctl -u cloudflared-quick -n 40 | grep trycloudflare"
echo "URL이 바뀌면 backend/.env 의 COUNSEL_FRONTEND_APP_URL, COUNSEL_API_CORS_ORIGINS 를 맞춘 뒤: sudo systemctl restart counsel-api"
