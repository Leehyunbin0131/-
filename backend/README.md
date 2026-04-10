# Career Counsel AI

**학생부·내신·모의고사(및 수능) 성적과 지원 선호**를 인테이크로 모은 뒤, 정리된 **모집결과·통계 데이터**와 LLM을 연결해 추천 요약과 후속 상담형 답변을 제공하는 백엔드입니다. “공개 자료 + 학생 프로필”을 맞춰 보는 **입시 컨설팅 지원**을 목적으로 하며, 법적·입학 확정 효력이 있는 판단을 대신하지는 않습니다.

이 프로젝트에는 다음이 포함됩니다.

- FastAPI 기반 입시 추천 백엔드
- 최소 구성의 Next.js 추천 프론트엔드
- LLM: **OpenAI**(Responses API·파일 인풋·웹 검색) 또는 **로컬 Ollama**(Python `ollama` SDK, 프롬프트 텍스트만)
- 5회로 집계되는 게스트 세션 기반 추천 횟수 추적
- `Data/` 원본 모집결과/모집요강을 `file inputs`로 읽는 추천 경로(OpenAI 프로바이더)
- 기숙사·등록금·캠퍼스 생활 정보를 위한 웹 보강 경로(OpenAI·웹 검색 활성화 시)

인테이크(초기 질문)는 무료입니다. 턴 차감은 시스템이 **최초 추천 요약**을 생성할 때 시작되며, 이후 후속 질문 답변마다 이어집니다.

## 프로젝트 구조

- `backend/`: FastAPI 앱, 수집(ingestion), 카탈로그, 추천 세션, 사용량
- `frontend/`: 랜딩, 세션, 추천 결과 UI가 있는 Next.js App Router 프론트엔드
- `Data/`: 원본 통계 자료
- `storage/`: 정규화 테이블, 세션, 게스트 상태, 사용량 상태, OpenAI 파일 캐시

## Windows: 원클릭 시작 / 종료

저장소 루트(`backend`와 `frontend`가 있는 폴더)에서:

- **`start-dev.bat`**을 더블클릭하면 창이 두 개 열립니다: API(`:8000`), 웹(`:3000`).
- **`stop-dev.bat`**을 더블클릭하면 포트 **8000**과 **3000**에서 대기 중인 프로세스를 종료합니다.

최초 설정은 `backend/`에서 `python -m pip install -e ".[dev]"`, `frontend/`에서 `npm install`이 여전히 필요합니다.

## 백엔드 빠른 시작

```bash
cd backend
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

### OpenAI 타임아웃

입시 요약은 **Responses API**에 여러 엑셀을 올리고 추론까지 하므로 **1분 이상** 걸릴 수 있습니다. `COUNSEL_REQUEST_TIMEOUT_SECONDS`(기본 60)만 쓰면 `ReadTimeout` / `APITimeoutError`가 납니다. **`COUNSEL_OPENAI_RESPONSES_TIMEOUT_SECONDS`(기본 900초)** 로 Responses·해당 파일 업로드만 별도로 길게 잡습니다.

### 로컬 Ollama(Gemma 등)

[Ollama](https://ollama.com/)를 설치한 뒤 데몬이 **실제로 떠 있어야** 합니다. Windows는 보통 **Ollama 데스크톱 앱**을 한 번 실행하면 트레이에서 서버가 같이 올라갑니다. Linux·macOS는 `ollama serve`를 켜 둡니다. 브라우저나 `curl`로 `http://127.0.0.1:11434/api/tags`가 열리는지 먼저 확인하세요. 사용할 채팅 모델은 `ollama pull gemma3:4b` 등으로 받고, `ollama list`에 보이는 태그를 `COUNSEL_OLLAMA_CHAT_MODEL`과 맞춥니다.

`.env`에 `COUNSEL_LLM_PROVIDER=ollama` 또는 `local`을 설정합니다. 앱 기동 시 Ollama 프로바이더면 **`/api/tags`에 대한 짧은 연결 검사**를 하며, 실패하면 **경고 로그**만 남기고 서버는 그대로 올라갑니다(요약 시에도 연결 실패 시 규칙 기반 요약으로 폴백).

**호스트 정리:** `COUNSEL_OLLAMA_HOST`가 비어 있으면 Ollama Python SDK와 동일하게 `OLLAMA_HOST` 환경 변수 또는 `http://127.0.0.1:11434`를 씁니다. 시스템에 `OLLAMA_HOST=0.0.0.0:11434`처럼 **바인드 주소**만 적혀 있으면, 백엔드는 클라이언트 접속용으로 **`127.0.0.1`로 바꿔** 붙습니다. **다른 PC의 Ollama**를 쓸 때는 `COUNSEL_OLLAMA_HOST`를 그 머신의 reachable 주소로 명시하세요.

Ollama 경로는 **엑셀을 Responses처럼 업로드하지 않습니다.** 모집결과 파일 경로·메타는 프롬프트 텍스트로만 전달되며, 호스팅 웹 검색도 사용하지 않습니다. OpenAI와 동일한 품질·근거를 기대하려면 `COUNSEL_LLM_PROVIDER=openai`(기본)와 API 키를 쓰는 편이 낫습니다.

### 추천 요약(`/complete`)과 `--reload`

`POST /api/v1/chat/session/{id}/complete`는 **백그라운드 작업**으로 처리됩니다. **HTTP 202**로 먼저 응답한 뒤, 클라이언트는 세션을 폴링하거나 완료 후 같은 엔드포인트를 다시 호출해 **200**과 전체 요약 본문을 받습니다.

OpenAI 프로바이더일 때는 파일 업로드·Responses·추론 때문에 **수 분** 걸릴 수 있습니다. Ollama 프로바이더일 때는 업로드 단계가 없지만, 모델·하드웨어에 따라 응답 시간은 달라집니다. 연결이 안 되면 로그에 Ollama 오류가 남고 **결정적(deterministic) 요약**으로 이어질 수 있습니다.

- **`--reload`를 켠 상태**에서는 파일이 바뀔 때마다 워커가 재시작되어 긴 작업이 끊길 수 있습니다. 추천 요약을 안정적으로 돌려보려면 `uvicorn app.main:app`(reload 없이) 실행을 권장합니다.
- **프로덕션**에서는 일반적으로 reload를 사용하지 않습니다.

기본 백엔드 URL:

- `http://127.0.0.1:8000`

## 프론트엔드 빠른 시작

```bash
cd frontend
npm install
npm run dev
```

기본 프론트엔드 URL:

- `http://127.0.0.1:3000`

로컬 개발 시 **`NEXT_PUBLIC_API_BASE_URL`은 비워 두세요**(`frontend/.env.local.example` 참고). Next.js 개발 서버가 `/api/v1/*`를 FastAPI(`BACKEND_INTERNAL_URL`, 기본값 `http://127.0.0.1:8000`)로 리라이트하므로 쿠키가 페이지와 같은 사이트(예: `localhost:3000`)에 유지됩니다. 앱을 `http://localhost:3000`으로 열어두고 `NEXT_PUBLIC_API_BASE_URL`을 `http://127.0.0.1:8000`으로 두면 게스트 쿠키가 전송되지 않아 세션 로드가 실패할 수 있습니다.

의도적으로 다른 오리진에서 API를 호출하고 CORS/쿠키 설정이 맞을 때만 전체 `NEXT_PUBLIC_API_BASE_URL`을 설정하세요.

## 외부에서 접속하기

기본값은 `127.0.0.1`(루프백)만 듣기 때문에 **같은 PC**에서만 접속됩니다. 다른 기기·인터넷에서 쓰려면 아래 중 상황에 맞는 방법을 씁니다.

### LAN(같은 Wi‑Fi 등)에서 접속

1. **백엔드**가 모든 네트워크 인터페이스에서 accept 하도록 실행합니다.

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

2. **프론트**(개발 서버)도 바깥에서 들어오는 연결을 받게 합니다.

```bash
cd frontend
npm run dev -- --hostname 0.0.0.0 --port 3000
```

3. 서버 PC의 **LAN IP**로 접속합니다(예: `http://192.168.0.12:3000`). `ipconfig`(Windows) / `ip a` 또는 `hostname -I`(Linux)로 주소를 확인합니다.

4. **백엔드 `.env`**에서 브라우저에 보이는 주소와 맞춥니다.  
   - `COUNSEL_FRONTEND_APP_URL=http://192.168.0.12:3000`  
   - `COUNSEL_API_CORS_ORIGINS`에 동일한 오리진을 포함합니다(쉼표로 여러 개 가능). 예: `http://192.168.0.12:3000`

5. **프론트 `frontend/.env.local`**에서 휴대폰 등으로 접속할 때 Next dev HMR 차단 경고를 없애려면, 접속에 쓰는 **호스트만** 콤마로 넣습니다. 예: `NEXT_ALLOWED_DEV_ORIGINS=192.168.0.12` (프로토콜 없이 IP 또는 호스트명). 개발 서버를 다시 띄웁니다.

6. **`NEXT_PUBLIC_API_BASE_URL`은 비운 채** 두면, 다른 기기의 브라우저는 `http://192.168.x.x:3000`으로만 요청하고 Next가 서버 쪽에서 `BACKEND_INTERNAL_URL`(기본 `http://127.0.0.1:8000`)로 백엔드에 붙습니다. 백엔드를 **다른 머신**에 둔 경우에만 `BACKEND_INTERNAL_URL`을 그 머신의 내부 주소로 바꿉니다.

7. **OS 방화벽**에서 TCP **3000**, **8000** 인바운드를 허용합니다.  
   - Windows: “고급 보안이 포함 Windows Defender 방화벽” → 인바운드 규칙 → 새 규칙(포트).  
   - Ubuntu 등: `sudo ufw allow 3000/tcp` 및 `sudo ufw allow 8000/tcp` 후 `sudo ufw reload`.

### 인터넷(공인 IP·도메인)으로 열기

- **집/사무실 공유기 뒤**라면 공유기 관리 페이지에서 **포트 포워딩**(WAN → 서버 PC의 3000 또는 역프록시용 80/443)을 설정하고, 위와 같이 `COUNSEL_FRONTEND_APP_URL`·`COUNSEL_API_CORS_ORIGINS`를 **`http://공인IP:포트` 또는 `https://도메인`**으로 맞춥니다. HTTP로 노출하는 것은 비밀번호·쿠키 탈취 위험이 있으므로 **가능하면 HTTPS + 도메인**을 쓰세요.
- **본격 운영**은 아래 [Linux: 프로덕션 호스팅](#linux-프로덕션-호스팅)처럼 Nginx(또는 Caddy)로 443을 받고 앱은 `127.0.0.1`에만 바인딩하는 방식이 안전합니다.
- **데모·잠깐 공유**만 필요하면 [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)·[ngrok](https://ngrok.com/) 등으로 로컬 `3000`만 터널링하고, 발급된 `https://....` URL을 `COUNSEL_FRONTEND_APP_URL`·`COUNSEL_API_CORS_ORIGINS`에 넣는 방법이 포트 개방 없이 단순합니다.

### 프로덕션에서 “외부 접속”

인터넷 사용자에게 서비스하려면 **도메인 + 80/443 + 역프록시** 구성이 일반적입니다. 절차·systemd·Nginx 예시는 [Linux: 프로덕션 호스팅](#linux-프로덕션-호스팅)을 따르고, DNS A/AAAA 레코드를 서버 공인 IP에 연결하면 됩니다.

## Linux: 프로덕션 호스팅

배포 시에도 **저장소 루트**에 `backend/`, `frontend/`, `Data/`, `storage/`가 함께 있어야 합니다. 백엔드의 `project_root`는 `backend` 폴더의 상위(저장소 루트)로 잡히므로, `Data/`·`storage/`를 다른 위치만 쓰려면 `COUNSEL_DATA_ROOT`, `COUNSEL_STORAGE_ROOT`로 절대 경로를 지정하세요.

### 1. 준비물

- Python **3.12+**, Node.js **18+**(LTS 권장), `npm` 또는 `pnpm`
- 방화벽에서 **80/443**(역프록시 사용 시)만 공개하고, 앱은 `127.0.0.1`에 바인딩하는 구성을 권장합니다.
- HTTPS(Let’s Encrypt 등)와 실제 도메인 — 외부 공개 운영 시 쿠키 보안을 위해 권장합니다.

### 2. 의존성 설치

```bash
cd /path/to/repo/backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

개발 전용 도구는 빼고 설치했습니다. 테스트까지 돌리려면 `pip install -e ".[dev]"`를 쓰면 됩니다.

```bash
cd /path/to/repo/frontend
npm ci
npm run build
```

### 3. 환경 변수(프로덕션)

- **백엔드** `backend/.env`: OpenAI 사용 시 `COUNSEL_OPENAI_API_KEY`, `COUNSEL_FRONTEND_APP_URL`(예: `https://your.domain`), `COUNSEL_API_CORS_ORIGINS`(프론트 공개 URL), HTTPS 사용 시 **`COUNSEL_COOKIE_SECURE=true`**, `COUNSEL_OPENAI_REASONING_EFFORT`, `COUNSEL_OPENAI_FILE_BATCH_SIZE` 등을 환경에 맞게 채웁니다. 서버에서만 Ollama를 쓸 경우 `COUNSEL_LLM_PROVIDER=ollama`와 Ollama 호스트·모델 변수를 추가합니다(자세한 목록은 아래 [환경 변수](#환경-변수)).
- **프론트** `frontend/.env.production`(또는 배포 플랫폼의 환경 변수): 같은 출처로 `/api/v1`를 쓸 때는 **`NEXT_PUBLIC_API_BASE_URL`을 비우고**, **`BACKEND_INTERNAL_URL=http://127.0.0.1:8000`**처럼 Next 서버만 백엔드에 붙입니다.

### 4. 프로세스 실행(수동 예시)

터미널 세션에서 확인할 때:

```bash
# 터미널 1 — 백엔드 (리로드 없음, 워커 수는 CPU에 맞게)
cd /path/to/repo/backend
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
```

```bash
# 터미널 2 — 프론트 (프로덕션 빌드)
cd /path/to/repo/frontend
npm run start
```

### 5. systemd로 상시 구동(예시)

`/etc/systemd/system/counsel-api.service`:

```ini
[Unit]
Description=Career Counsel API (uvicorn)
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/repo/backend
EnvironmentFile=/path/to/repo/backend/.env
ExecStart=/path/to/repo/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/counsel-web.service`:

```ini
[Unit]
Description=Career Counsel Next.js
After=network.target counsel-api.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/repo/frontend
EnvironmentFile=-/path/to/repo/frontend/.env.production
ExecStart=/usr/bin/npm run start
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

`sudo systemctl daemon-reload && sudo systemctl enable --now counsel-api counsel-web` 후 `journalctl -u counsel-api -f`로 로그를 확인합니다. `User`·경로·`ExecStart`의 `npm` 경로(`which npm`)는 서버에 맞게 바꿉니다.

### 6. Nginx 역프록시(HTTPS)

브라우저는 **한 도메인**(예: `https://your.domain`)만 보게 하고, Nginx가 `127.0.0.1:3000`으로 넘기면 Next의 `/api/v1/*` 리라이트가 내부에서 FastAPI(`BACKEND_INTERNAL_URL`)로 전달됩니다. SSL 인증서는 certbot 등으로 설정합니다.

```nginx
server {
    listen 443 ssl http2;
    server_name your.domain;

    # ssl_certificate / ssl_certificate_key ...

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

현재 제품 경로에는 별도 결제/웹훅 엔드포인트가 없습니다.

### 7. 그 외

- **스토리지**: 현재 구현은 로컬 `storage/` 파일에 상태가 쌓입니다. 백업·디스크 용량·다중 인스턴스(수평 확장)는 별도 설계가 필요합니다.
- **PaaS**(Railway, Fly.io, Render 등)는 각 플랫폼의 “빌드 커맨드 / 시작 커맨드 / 환경 변수”에 위 내용을 옮기면 됩니다. 두 프로세스(또는 컨테이너) 모두 같은 `BACKEND_INTERNAL_URL`·`.env` 규칙을 지키면 됩니다.

## 환경 변수

백엔드 변수는 `COUNSEL_` 접두사를 사용합니다. 전체 예시는 `backend/.env.example`을 참고하세요.

### 공통

- `COUNSEL_FRONTEND_APP_URL`
- `COUNSEL_API_CORS_ORIGINS`
- `COUNSEL_TRIAL_TURN_LIMIT`
- `COUNSEL_FOLLOWUP_CONVERSATION_MAX_MESSAGES` (기본 `0`: 후속 LLM 컨텍스트는 세션 요약 이후 약 30턴 분량의 채팅 메시지를 포함; 수동 상한을 두려면 양수로 설정)
- `COUNSEL_COOKIE_SECURE` (HTTPS 운영 시 `true` 권장)
- `COUNSEL_DATA_ROOT`, `COUNSEL_STORAGE_ROOT` (선택; 기본은 저장소 루트 기준 `Data/`, `storage/`)

### LLM 프로바이더

- `COUNSEL_LLM_PROVIDER`: `openai`(기본) · `ollama` · `local`(`ollama`와 동일)

### OpenAI (`COUNSEL_LLM_PROVIDER=openai`)

- `COUNSEL_OPENAI_API_KEY`
- `COUNSEL_OPENAI_CHAT_MODEL`, `COUNSEL_OPENAI_EMBEDDING_MODEL`
- `COUNSEL_REQUEST_TIMEOUT_SECONDS` (일반 API 타임아웃)
- `COUNSEL_OPENAI_RESPONSES_TIMEOUT_SECONDS` (Responses·긴 읽기; 기본 900초 권장)
- `COUNSEL_OPENAI_REASONING_EFFORT`, `COUNSEL_OPENAI_FILE_BATCH_SIZE`
- `COUNSEL_OPENAI_SUMMARY_MAX_CANDIDATE_FILES` (요약 후보 엑셀 상한)
- `COUNSEL_OPENAI_RESPONSES_TEMPERATURE` (선택; 일부 모델은 미설정이 안전)
- `COUNSEL_OPENAI_WEB_SEARCH_ENABLED` (기본 `true`: 기숙사·등록금 등 생활 정보 질문에서 웹 보강)
- `COUNSEL_OPENAI_WEB_SEARCH_MODEL` (선택; `web_search`를 지원하는 모델)

### Ollama (`COUNSEL_LLM_PROVIDER=ollama` 또는 `local`)

- `COUNSEL_OLLAMA_HOST` (선택; 비우면 `OLLAMA_HOST` 또는 `http://127.0.0.1:11434`)
- `COUNSEL_OLLAMA_CHAT_MODEL` (기본 `gemma3:4b`; `ollama list` 태그와 일치)
- `COUNSEL_OLLAMA_EMBED_MODEL` (기본 `nomic-embed-text`)
- `COUNSEL_OLLAMA_TIMEOUT_SECONDS`, `COUNSEL_OLLAMA_CHAT_TEMPERATURE`

권장 개발 기본값:

- 백엔드: `backend/.env.example` 참고
- 프론트엔드: `frontend/.env.local.example` 참고

## 데이터 수집(ingestion)

- **엔드포인트:** `POST /api/v1/ingestion/run` — `Data/` 아래 스프레드시트를 스캔해 `storage/catalog/manifest.json`과 `storage/silver/...` parquet를 갱신합니다.
- **`storage/`는 Git에 올라가지 않습니다** (`.gitignore`). 저장소를 클론한 다른 머신·서버에서는 `Data/`만 동기화되어 있어도 카탈로그가 비어 있으므로, **배포·로컬 첫 설정 시 ingestion을 반드시 한 번 실행**하세요.
- 엑셀 **폴더 구조·파일명**은 지역 필터(영남권 등)와 맞물리므로 [`../Data/README.md`](../Data/README.md)를 따르는 것을 권장합니다. `Data/` 경로를 바꾼 뒤에도 ingestion을 다시 돌려야 합니다.

백엔드가 떠 있지 않을 때 저장소 루트의 `Data/`를 기준으로 로컬에서만 돌리려면:

```bash
cd backend
python -c "from app.config import Settings; from app.dependencies import ServiceContainer; s=Settings(); s.ensure_storage_dirs(); ServiceContainer(s).ingestion_pipeline.run()"
```

## 추천 세션 흐름

1. `POST /api/v1/ingestion/run`으로 수집 실행
2. `POST /api/v1/chat/session/start`로 게스트 세션 시작
3. `POST /api/v1/chat/session/{session_id}/answer`로 인테이크 질문에 답변
4. `POST /api/v1/chat/session/{session_id}/complete`로 최초 추천 요약 생성
5. `POST /api/v1/chat/session/{session_id}/message`로 후속 비교/생활 질문 이어가기
6. 무료 집계 5턴이 소진되면 백엔드가 추가 질문을 제한

## API 목록

- `GET /health`
- `GET /api/v1/catalog/datasets`
- `GET /api/v1/catalog/tables`
- `POST /api/v1/ingestion/run`
- `POST /api/v1/chat/session/start`
- `POST /api/v1/chat/session/{session_id}/answer`
- `GET /api/v1/chat/session/{session_id}`
- `POST /api/v1/chat/session/{session_id}/complete`
- `POST /api/v1/chat/session/{session_id}/message`

## 개발 시 참고

- 게스트 식별은 HttpOnly 쿠키로 추적
- 턴 집계의 단일 진실 소스(single source of truth)는 백엔드
- 전국 파일이 많아지면 `COUNSEL_OPENAI_FILE_BATCH_SIZE`에 따라 여러 배치로 나눠 추천 후 서버에서 합성(OpenAI 프로바이더)
- `storage/llm/openai_file_cache.json`에 file hash 기준 `file_id` 캐시를 유지(OpenAI)
- Python 의존성에 `ollama` 패키지가 포함되어 있으며, 로컬 모델 경로에서만 사용됩니다

## 테스트

백엔드:

```bash
cd backend
python -m pytest
```

`tests/conftest.py`에서 **`COUNSEL_LLM_PROVIDER=openai`로 고정**하므로, 로컬 `backend/.env`에 `ollama`를 써도 API 통합 테스트는 OpenAI 프로바이더·모킹 경로를 타며 깨지지 않습니다.

프론트엔드:

```bash
cd frontend
npm run build
```

## 저장소 레이아웃

- `storage/catalog/manifest.json`
- `storage/audit/answer_traces.jsonl`
- `storage/sessions/<session_id>.json`
- `storage/auth/state.json`
- `storage/llm/openai_file_cache.json`
- `storage/silver/<dataset_id>/<snapshot_date>/*.parquet`
