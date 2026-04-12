#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RUN_USER="${SUDO_USER:-$USER}"
RUN_GROUP="$(id -gn "$RUN_USER")"
NPM_BIN="$(command -v npm)"

if [[ ! -x "$ROOT/backend/.venv/bin/uvicorn" ]]; then
  echo "backend/.venv/bin/uvicorn 을 찾지 못했습니다. 먼저 backend 가상환경을 준비하세요." >&2
  exit 1
fi

if [[ ! -f "$ROOT/frontend/package.json" ]]; then
  echo "frontend/package.json 을 찾지 못했습니다." >&2
  exit 1
fi

if [[ ! -d "$ROOT/frontend/.next" ]]; then
  echo "==> Next.js 프로덕션 빌드"
  (
    cd "$ROOT/frontend"
    npm run build
  )
fi

api_unit="$(mktemp)"
web_unit="$(mktemp)"
trap 'rm -f "$api_unit" "$web_unit"' EXIT

sed \
  -e "s|__ROOT__|$ROOT|g" \
  -e "s|__USER__|$RUN_USER|g" \
  -e "s|__GROUP__|$RUN_GROUP|g" \
  "$ROOT/deploy/systemd/counsel-api.service.template" >"$api_unit"

sed \
  -e "s|__ROOT__|$ROOT|g" \
  -e "s|__USER__|$RUN_USER|g" \
  -e "s|__GROUP__|$RUN_GROUP|g" \
  -e "s|__NPM__|$NPM_BIN|g" \
  "$ROOT/deploy/systemd/counsel-web.service.template" >"$web_unit"

echo "==> counsel-api / counsel-web systemd 유닛 설치"
sudo install -m 644 "$api_unit" /etc/systemd/system/counsel-api.service
sudo install -m 644 "$web_unit" /etc/systemd/system/counsel-web.service

sudo systemctl daemon-reload
sudo systemctl enable --now counsel-api.service counsel-web.service

echo ""
echo "상태 확인:"
echo "  sudo systemctl status counsel-api.service --no-pager"
echo "  sudo systemctl status counsel-web.service --no-pager"
