# Career Counsel AI

This project now includes:

- a FastAPI counseling backend
- a minimal Next.js counseling frontend
- guest trial tracking with 5 counted turns
- email verification before payment
- Stripe Checkout plus webhook-based 30-turn entitlement

The intake questions are free. Turn deduction starts when the system generates
the initial counseling summary, then continues for each follow-up counseling
answer.

## Project Layout

- `backend/`: FastAPI app, ingestion, retrieval, counseling, auth, usage, billing
- `frontend/`: Next.js App Router frontend with landing, session, paywall, and checkout pages
- `Data/`: raw statistical sources
- `storage/`: normalized tables, sessions, auth state, usage state, billing state

## Windows: one-click start / stop

From the repository root (folder that contains `backend` and `frontend`):

- Double-click **`start-dev.bat`** to open two windows: API (`:8000`) and web (`:3000`).
- Double-click **`stop-dev.bat`** to stop whatever is listening on ports **8000** and **3000**.

First-time setup still needs `python -m pip install -e ".[dev]"` under `backend/` and `npm install` under `frontend/`.

## Backend Quick Start

```bash
cd backend
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Default backend URL:

- `http://127.0.0.1:8000`

## Frontend Quick Start

```bash
cd frontend
npm install
npm run dev
```

Default frontend URL:

- `http://127.0.0.1:3000`

For local development, **leave `NEXT_PUBLIC_API_BASE_URL` empty** (see `frontend/.env.local.example`). The Next.js dev server rewrites `/api/v1/*` to FastAPI (`BACKEND_INTERNAL_URL`, default `http://127.0.0.1:8000`) so cookies stay on the same site as the page (e.g. `localhost:3000`). If you set `NEXT_PUBLIC_API_BASE_URL` to `http://127.0.0.1:8000` while opening the app at `http://localhost:3000`, guest cookies may not be sent and session load can fail.

Only set a full `NEXT_PUBLIC_API_BASE_URL` when you intentionally call the API from another origin and have matching CORS/cookie settings.

## Environment Variables

Backend variables use the `COUNSEL_` prefix.

Important backend settings:

- `COUNSEL_OPENAI_API_KEY`
- `COUNSEL_DEFAULT_LLM_PROVIDER`
- `COUNSEL_FRONTEND_APP_URL`
- `COUNSEL_API_CORS_ORIGINS`
- `COUNSEL_TRIAL_TURN_LIMIT`
- `COUNSEL_PAID_TURN_PACK_SIZE`
- `COUNSEL_PAID_PACK_PRICE_CENTS`
- `COUNSEL_STRIPE_SECRET_KEY`
- `COUNSEL_STRIPE_WEBHOOK_SECRET`
- `COUNSEL_STRIPE_PRICE_ID`
- `COUNSEL_DEV_RETURN_EMAIL_CODE`

Recommended development defaults:

- backend: see `backend/.env.example`
- frontend: see `frontend/.env.local.example`

## Counseling + Billing Flow

1. Run ingestion with `POST /api/v1/ingestion/run`
2. Start a guest session with `POST /api/v1/chat/session/start`
3. Answer intake questions with `POST /api/v1/chat/session/{session_id}/answer`
4. Generate the initial counseling summary with `POST /api/v1/chat/session/{session_id}/complete`
5. Continue follow-up counseling with `POST /api/v1/chat/session/{session_id}/message`
6. When the 5 free counted turns are exhausted, the backend returns upgrade-required state
7. Start email verification with `POST /api/v1/auth/email/start`
8. Verify email with `POST /api/v1/auth/email/verify`
9. Create Stripe Checkout with `POST /api/v1/billing/checkout`
10. Grant the 30-turn entitlement only after `POST /api/v1/webhooks/stripe`

## API Surface

- `GET /health`
- `GET /api/v1/catalog/datasets`
- `GET /api/v1/catalog/tables`
- `POST /api/v1/ingestion/run`
- `POST /api/v1/chat/session/start`
- `POST /api/v1/chat/session/{session_id}/answer`
- `GET /api/v1/chat/session/{session_id}`
- `POST /api/v1/chat/session/{session_id}/complete`
- `POST /api/v1/chat/session/{session_id}/message`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/email/start`
- `POST /api/v1/auth/email/verify`
- `GET /api/v1/billing/entitlement`
- `POST /api/v1/billing/checkout`
- `POST /api/v1/webhooks/stripe`

## Development Notes

- guest identity is tracked with an HttpOnly cookie
- user identity is tracked with a separate HttpOnly cookie after email verification
- the backend is the source of truth for turn counting and upgrade requirements
- Stripe success redirects are not trusted by themselves; webhook confirmation is required
- in development, email verification can return the code directly if `COUNSEL_DEV_RETURN_EMAIL_CODE=true`

## Tests

Backend:

```bash
cd backend
python -m pytest
```

Frontend:

```bash
cd frontend
npm run build
```

## Storage Layout

- `storage/catalog/manifest.json`
- `storage/query/warehouse.duckdb`
- `storage/retrieval/index.json`
- `storage/audit/answer_traces.jsonl`
- `storage/sessions/<session_id>.json`
- `storage/auth/state.json`
- `storage/usage/state.json`
- `storage/billing/state.json`
- `storage/silver/<dataset_id>/<snapshot_date>/*.parquet`
