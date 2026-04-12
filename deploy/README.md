# 배포 보조 스크립트

| 경로 | 용도 |
|------|------|
| `nginx/` | Nginx 스니펫·사이트 설정 예시 |
| `cloudflared/` | Cloudflare Tunnel(토큰 / Quick Tunnel) systemd 유닛 및 설치 스크립트 |
| `scripts/` | 한국 IP CIDR 갱신 등 |
| `cron/` | 주간 CIDR 갱신 cron 링크 설치 |

비밀번호·API 키·터널 토큰은 저장소에 넣지 말고 서버의 `backend/.env`, `/etc/default/cloudflared` 등에만 두세요.
