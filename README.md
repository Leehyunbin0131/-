# Career Counsel AI

모집결과·프로필을 바탕으로 입시 추천 요약과 후속 질의를 돕는 풀스택 앱입니다. 백엔드는 **FastAPI**, 프론트는 **Next.js(App Router)** 입니다.

## 구성

| 경로 | 설명 |
|------|------|
| [`backend/`](backend/) | API, 수집(ingestion), 카탈로그, 상담 세션, LLM 연동 |
| [`frontend/`](frontend/) | 랜딩·세션·추천 결과 UI |
| `Data/` | 원본 모집결과 등(로컬 데이터; Git 정책은 팀에 맞게) |
| `storage/` | 런타임 상태(`.gitignore`; 카탈로그·세션·캐시 등) |

LLM은 **OpenAI**(파일 인풋·웹 검색) 또는 **로컬 Ollama** 중 선택합니다. 자세한 설정·타임아웃·배포는 **[backend/README.md](backend/README.md)** 를 참고하세요.

## 필요 환경

- Python **3.12+**
- Node.js **18+**(LTS 권장)

## 빠른 시작 (Windows)

저장소 **루트**에서:

1. `start-dev.bat` — API `:8000`과 웹 `:3000`을 각각 띄웁니다.  
2. 최초 1회: `backend`에서 `python -m pip install -e ".[dev]"`, `frontend`에서 `npm install`.

종료는 `stop-dev.bat` (포트 8000·3000).

## 수동 실행

```bash
# 터미널 1
cd backend
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload

# 터미널 2
cd frontend
npm install
npm run dev
```

- API: `http://127.0.0.1:8000`  
- 웹: `http://127.0.0.1:3000`  

백엔드 환경 변수는 `backend/.env`에 두고, 템플릿은 [`backend/.env.example`](backend/.env.example)입니다. **`.env`는 Git에 올리지 마세요.**

## 문서

- [backend/README.md](backend/README.md) — 환경 변수, Ollama, `/complete` 비동기 요약, CORS·LAN·프로덕션(Nginx·systemd), 테스트  
- [frontend/.env.local.example](frontend/.env.local.example) — 로컬 프록시·쿠키 관련 안내

## 라이선스

별도 `LICENSE`가 없다면 조직·프로젝트 정책에 따릅니다.
