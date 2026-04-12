# 배포 보조 스크립트

`deploy/`는 운영 서버를 빠르게 구성할 수 있도록 **Nginx**, **Cloudflare Tunnel**, **한국 IP 허용 정책**, **주기적 CIDR 갱신**에 필요한 보조 파일을 모아 둔 디렉터리입니다.

## 구성

| 경로 | 용도 |
|------|------|
| `nginx/` | Nginx 스니펫, 실제 서비스용 사이트 설정 예시 |
| `cloudflared/` | Cloudflare Tunnel용 systemd 유닛과 설치 스크립트 |
| `systemd/` | `counsel-api`, `counsel-web` 상시 구동용 유닛 템플릿과 설치 스크립트 |
| `scripts/` | 한국 IP CIDR 갱신 등 운영 스크립트 |
| `cron/` | 주간 자동 갱신용 cron 링크 설치 스크립트 |

## 포함된 내용

- **공인 IP 직접 노출** 시 사용할 수 있는 Nginx 설정
- **Cloudflare Quick Tunnel / named tunnel** 전환에 필요한 systemd 유닛
- **서버 재부팅 시 자동 시작**되도록 `counsel-api`, `counsel-web` 유닛 설치 스크립트
- **Quick Tunnel URL 자동 동기화**(`README.md`, `backend/.env`, `counsel-api` 재시작)
- **한국 IP만 허용**하는 geo 기반 Nginx 보조 설정
- **ipdeny** 기반 KR CIDR 주기 갱신 스크립트

## 운영 시 주의사항

- 비밀번호, API 키, 터널 토큰은 저장소에 넣지 말고 `backend/.env`, `/etc/default/cloudflared` 같은 **서버 로컬 파일**에만 두세요.
- `deploy/`의 스크립트는 서버 환경을 가정하고 있으므로, 적용 전 대상 경로와 systemd 서비스 이름을 한 번 더 확인하는 것이 좋습니다.
- Quick Tunnel 기반 운영이라면 먼저 `deploy/systemd/install-counsel-services.sh`, 그다음 `deploy/cloudflared/install-cloudflare-quick-tunnel.sh`를 적용하면 재부팅 자동 시작과 README URL 동기화를 함께 설정할 수 있습니다.
