# Career Counsel AI

대학 입시를 준비하는 학생·보호자가 **학생부 활동과 교과 성취(내신)**, **모의고사·수능 등 성적 정보**, 그리고 **지원 전형·지역·선호**를 한곳에 정리한 뒤, 실제 **공개된 모집결과·통계 자료**와 맞춰 보며 방향을 잡을 수 있도록 돕는 풀스택 앱입니다. 백엔드는 **FastAPI**, 프론트는 **Next.js(App Router)** 입니다.

## 왜 이 프로젝트인가

수시·정시를 준비할 때 필요한 정보는 대학별 모집요강·전년도 모집결과·경쟁률·컷 등으로 흩어져 있고, “우리 아이 **학생부·내신·모의고사** 조건으로 어디를 어떤 전형으로 볼지”를 정리하려면 상담 시간이 많이 들거나 자료를 일일이 대조해야 합니다. 이 프로젝트는 그 과정을 **구조화된 인테이크(질문 흐름)** 로 받아, 보유한 **모집결과 데이터(`Data/`)** 와 LLM을 이용해 **추천 후보 요약**과 **후속 질문(비교·생활 정보 등)** 에 답할 수 있는 **입시 컨설팅 보조 도구**를 목표로 합니다.

- **입력 쪽:** 재학 상태, 관심 계열, **내신(교과/전교과 등급)**, **모의고사·수능 성적**, 희망 전형·지역, 제약 조건(거리·기숙사 등)을 단계적으로 수집합니다.  
- **근거 쪽:** 시스템이 카탈로그에 등록된 모집결과·통계 파일을 후보로 골라(OpenAI 사용 시 파일까지 직접 참조), 그 맥락에서 요약·설명을 생성합니다.  
- **한계:** 합격을 보장하지 않으며, 최종 지원은 반드시 공식 모집요강·입학처 안내와 본인 판단을 따릅니다.

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
