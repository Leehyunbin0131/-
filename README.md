<p align="center">
  <img src="ImageAZ.png" alt="Career Counsel AI" width="960" />
</p>

# Career Counsel AI

<p align="center">
  <b>체험하기</b> ·
  <a href="https://surveys-sophisticated-barn-tickets.trycloudflare.com"><b>라이브 데모 (HTTPS)</b></a>
  <br /><br />
  <sub><i>현재 데모는 Cloudflare Quick Tunnel 주소를 사용합니다. `cloudflared-quick`가 재시작되면 저장소의 자동 동기화 스크립트가 `README.md`와 `backend/.env`를 갱신하고, `README.md`가 바뀐 경우 10초 뒤 자동 커밋/푸시까지 수행합니다.</i></sub>
</p>

---

Career Counsel AI는 **학생부·내신·모의고사(및 수능) 성적**, **희망 전형·지역·조건**을 구조화해 입력받고, 실제 **공개 모집결과·요강 데이터**와 LLM을 연결해 대학·학과·전형 후보를 정리해 주는 **입시 상담 보조 풀스택 애플리케이션**입니다. 프론트엔드는 **Next.js(App Router)**, 백엔드는 **FastAPI**로 구성되어 있습니다.

## 한눈에 보기

- **질문 흐름 중심 인테이크:** 복잡한 입시 조건을 단계적으로 정리합니다.
- **근거 기반 추천:** `Data/`에 보관된 실제 모집결과 파일을 우선 읽고 요약합니다.
- **상담형 후속 질의:** 비교, 생활 정보, 전형 차이 같은 질문을 이어서 받을 수 있습니다.
- **운영 친화적 구조:** `Data/` 원본과 `storage/` 산출물을 분리해 배포와 재생성을 단순화했습니다.

## 현재 지원 범위

- **현재 데이터 범위는 경북권 일부 대학 중심**입니다.
- 추천 품질은 `Data/`에 들어 있는 모집결과 원본 범위에 직접 영향을 받습니다.
- 지원 범위를 넓히려면 원본 파일을 추가한 뒤 **ingestion을 다시 실행**하면 됩니다.

## 왜 이 프로젝트인가

입시 준비 과정에서는 대학별 모집요강, 전년도 모집결과, 경쟁률, 충원 현황, 전형별 컷 같은 자료가 여러 곳에 흩어져 있습니다. 실제 상담에서는 "이 학생의 **내신·모의고사·학생부 조건**으로 어떤 대학과 전형을 우선 봐야 하는가"를 정리하는 데 많은 시간이 들고, 보호자와 학생이 자료를 직접 대조하기도 쉽지 않습니다.

이 프로젝트는 그 과정을 **구조화된 질문 흐름 + 공개 자료 근거 + LLM 요약**으로 재구성해, 사람이 검토하기 좋은 초안과 비교 포인트를 빠르게 만드는 것을 목표로 합니다.

- **입력:** 재학 상태, 관심 계열, 교과 성취, 모의고사·수능 성적, 희망 지역, 기숙사 여부 같은 조건을 단계적으로 수집합니다.
- **근거:** 카탈로그에 등록된 모집결과 파일과 디스크의 최신 원본을 후보로 골라, 그 맥락에서 설명을 생성합니다.
- **주의:** 이 서비스는 합격을 보장하지 않으며, 최종 지원 판단은 반드시 공식 모집요강과 입학처 안내를 기준으로 해야 합니다.

## 저장소 구성

| 경로 | 설명 |
|------|------|
| [`backend/`](backend/) | FastAPI API, ingestion, 카탈로그, 상담 세션, LLM 연동 |
| [`frontend/`](frontend/) | Next.js 기반 랜딩, 세션, 추천 결과 UI |
| [`Data/`](Data/) | 모집결과·요강 원본 데이터 |
| `storage/` | 런타임 상태와 재생성 가능한 산출물 (Git 제외) |
| [`deploy/`](deploy/) | Nginx, Cloudflare Tunnel, 한국 IP 필터링 등 배포 보조 스크립트 |

## 설계 포인트

### FastAPI + Next.js 분리

- **백엔드**는 입시 로직, 파일 후보 선정, 세션·사용량, LLM 호출처럼 상태와 규칙이 많은 영역을 담당합니다.
- **프론트엔드**는 질문 흐름, 결과 UI, 쿠키 기반 세션 유지, 사용성 개선에 집중합니다.
- Next가 `/api/v1/*`를 내부에서 FastAPI로 프록시하면, 브라우저는 **한 출처(same-site)** 만 보게 되어 쿠키와 CORS 구성이 단순해집니다.

### `Data/`와 `storage/` 분리

- `Data/`는 사람이 관리하는 **원본**입니다.
- `storage/`는 ingestion 결과, 세션, 캐시처럼 **재생성 가능한 산출물**입니다.
- 이 구조 덕분에 원본과 캐시가 뒤섞이지 않고, 서버 이전이나 재배포 시에도 운영 흐름이 명확해집니다.

### "원문 파일을 직접 읽는" 추천 경로

입시 추천은 전형명, 등급, 경쟁률, 충원, 환산점수처럼 **세부 수치가 정확해야 신뢰를 얻을 수 있는 문제**입니다. 이 프로젝트는 요약문만 미리 만들어 쓰기보다, 가능한 경우 OpenAI Responses API의 `input_file` 경로를 통해 **실제 xlsx/pdf 원문을 직접 참조**하게 합니다.

같은 학교·연도·전형 묶음에 엑셀과 PDF가 동시에 있으면, 일반적으로 **엑셀을 우선**해 토큰 낭비를 줄이고 표 구조를 더 안정적으로 읽게 합니다.

### 비동기 추천 생성

파일 업로드와 LLM 추론은 수 분이 걸릴 수 있어 `/complete`와 `/message`는 **백그라운드 작업 + 202 응답** 패턴을 사용합니다. 이 방식은 브라우저·프록시 타임아웃을 줄이고, 재시도와 진행 상태 확인을 더 안정적으로 처리합니다.

## 빠른 시작

### 필요 환경

- Python **3.12+**
- Node.js **20.9+**

### Windows

저장소 루트에서:

1. `backend`에서 `python -m pip install -e ".[dev]"`
2. `frontend`에서 `npm install`
3. `start-dev.bat` 실행

종료는 `stop-dev.bat`으로 할 수 있습니다.

### 수동 실행

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
- Web: `http://127.0.0.1:3000`

백엔드 환경 변수는 `backend/.env`, 프론트 개발 환경 변수는 `frontend/.env.local`을 사용합니다. 템플릿은 각각 `backend/.env.example`, `frontend/.env.local.example`을 참고하세요.

## 문서 가이드

- [`backend/README.md`](backend/README.md): 아키텍처, 환경 변수, ingestion, API, 운영
- [`Data/README.md`](Data/README.md): 데이터 폴더 구조와 파일 배치 규칙
- [`deploy/README.md`](deploy/README.md): 배포 보조 스크립트와 운영 주의사항

## 배포 참고

- 로컬/사설망/공인 IP 노출 방식 모두 지원할 수 있도록 설계되어 있습니다.
- 현재 저장소에는 **Nginx, Cloudflare Tunnel, 한국 IP 필터링**을 위한 보조 스크립트가 포함되어 있습니다.
- 서버 상시 구동용 `systemd` 설치 스크립트는 `deploy/systemd/install-counsel-services.sh`에 있습니다.
- Quick Tunnel 주소 자동 동기화 설치 스크립트는 `deploy/cloudflared/install-cloudflare-quick-tunnel.sh`에 있습니다.
- 운영 환경에서는 `storage/`가 비어 있을 수 있으므로, **서버 배포 후 ingestion을 최소 1회 실행**해야 추천이 정상 동작합니다.

## 라이선스

별도 `LICENSE`가 없다면 조직 또는 프로젝트 정책을 따릅니다.
