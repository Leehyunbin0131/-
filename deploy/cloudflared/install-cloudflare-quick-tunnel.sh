#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SYNC_INSTALL_DIR="/usr/local/lib/career-counsel"
SYNC_ENV_FILE="/etc/default/career-counsel-quick-tunnel-sync"
RUN_USER="${SUDO_USER:-$USER}"
RUN_GROUP="$(id -gn "$RUN_USER")"
RUN_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"
SYNC_UNIT_TMP="$(mktemp)"
trap 'rm -f "$SYNC_UNIT_TMP"' EXIT

sudo systemctl disable --now cloudflared 2>/dev/null || true

echo "==> Quick Tunnel sync helper 설치"
sudo install -d -m 755 "$SYNC_INSTALL_DIR"
sudo install -m 755 "$ROOT/deploy/cloudflared/sync-quick-tunnel-url.py" \
  "$SYNC_INSTALL_DIR/sync-quick-tunnel-url.py"

echo "==> cloudflared-quick systemd 유닛 설치"
sudo install -m 644 "$ROOT/deploy/cloudflared/cloudflared-quick.service" \
  /etc/systemd/system/cloudflared-quick.service
sed \
  -e "s|__ROOT__|$ROOT|g" \
  -e "s|__USER__|$RUN_USER|g" \
  -e "s|__GROUP__|$RUN_GROUP|g" \
  -e "s|__HOME__|$RUN_HOME|g" \
  "$ROOT/deploy/cloudflared/cloudflared-quick-sync.service" >"$SYNC_UNIT_TMP"
sudo install -m 644 "$SYNC_UNIT_TMP" /etc/systemd/system/cloudflared-quick-sync.service

echo "==> Quick Tunnel sync 환경 파일 생성"
sudo tee "$SYNC_ENV_FILE" >/dev/null <<EOF
CAREER_COUNSEL_REPO_ROOT=$ROOT
CAREER_COUNSEL_BACKEND_ENV=$ROOT/backend/.env
CAREER_COUNSEL_README_PATH=$ROOT/README.md
CAREER_COUNSEL_QUICK_TUNNEL_UNIT=cloudflared-quick.service
CAREER_COUNSEL_API_SERVICE=counsel-api.service
CAREER_COUNSEL_WAIT_SECONDS=60
CAREER_COUNSEL_GIT_AUTO_PUSH=true
CAREER_COUNSEL_GIT_PUSH_DELAY_SECONDS=10
CAREER_COUNSEL_GIT_REMOTE=origin
CAREER_COUNSEL_GIT_BRANCH=main
CAREER_COUNSEL_GIT_COMMIT_MESSAGE=docs: refresh live demo URL
EOF
sudo chmod 644 "$SYNC_ENV_FILE"

sudo systemctl daemon-reload
sudo systemctl enable cloudflared-quick
sudo systemctl restart cloudflared-quick
sleep 3

echo "==> 최신 Quick Tunnel 주소를 README 및 backend/.env 에 반영"
sudo systemctl start cloudflared-quick-sync.service

echo "발급된 주소 (서비스 재시작 시 바뀔 수 있음):"
sudo -u "$RUN_USER" env HOME="$RUN_HOME" python3 "$SYNC_INSTALL_DIR/sync-quick-tunnel-url.py" \
  --repo-root "$ROOT" \
  --dry-run \
  --git-auto-push \
  --skip-restart-api || true
echo ""
echo "수동 동기화: sudo systemctl start cloudflared-quick-sync.service"
echo "로그 확인: sudo journalctl -u cloudflared-quick -n 40 | grep trycloudflare"
