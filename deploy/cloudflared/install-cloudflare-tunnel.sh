#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo "==> Nginx: 실제 클라이언트 IP (Tunnel + 한국 geo 호환)"
sudo cp "$ROOT/deploy/nginx/20-cloudflared-real-ip.conf" /etc/nginx/conf.d/20-cloudflared-real-ip.conf
sudo chmod 644 /etc/nginx/conf.d/20-cloudflared-real-ip.conf

echo "==> cloudflared systemd 유닛"
sudo cp "$ROOT/deploy/cloudflared/cloudflared.service" /etc/systemd/system/cloudflared.service
sudo chmod 644 /etc/systemd/system/cloudflared.service

if [[ ! -f /etc/default/cloudflared ]]; then
  echo "==> /etc/default/cloudflared 생성 (토큰을 채운 뒤: sudo systemctl enable --now cloudflared)"
  sudo cp "$ROOT/deploy/cloudflared/default.cloudflared" /etc/default/cloudflared
  sudo chmod 600 /etc/default/cloudflared
fi

sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl reload nginx

echo ""
echo "다음 단계:"
echo "  1) https://one.dash.cloudflare.com/ → Zero Trust → Networks → Tunnels → Create tunnel"
echo "  2) Public hostname: 예) counsel.도메인.com → http://localhost:80 (또는 127.0.0.1:80)"
echo "  3) 표시된 토큰을 sudo nano /etc/default/cloudflared 에 붙여넣기"
echo "  4) 백엔드 URL 맞추기: backend/.env 의 COUNSEL_FRONTEND_APP_URL, COUNSEL_API_CORS_ORIGINS 를"
echo "     https://(위에서 연 Public hostname) 로 변경 후: sudo systemctl restart counsel-api"
echo "  5) sudo systemctl enable --now cloudflared"
echo ""
if systemctl is-active --quiet cloudflared 2>/dev/null; then
  sudo systemctl restart cloudflared || true
fi
