import type {
  AuthState,
  CheckoutResponse,
  EmailStartResponse,
  EmailVerifyResponse,
  FollowupResponse,
  SessionProgressResponse,
  SessionStatusResponse,
  SessionSummaryResponse,
} from "@/lib/types";

/**
 * Empty string = same origin (recommended). Next rewrites /api/v1/* to the FastAPI server
 * so Set-Cookie from the API is stored for the page host (e.g. localhost:3000), avoiding
 * localhost vs 127.0.0.1 cross-site cookie drops with SameSite=Lax.
 */
const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? ""
).replace(/\/$/, "");

type HttpMethod = "GET" | "POST";

async function request<T>(
  path: string,
  init?: {
    method?: HttpMethod;
    body?: unknown;
    noStore?: boolean;
  },
): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const response = await fetch(url, {
    method: init?.method ?? "GET",
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    body: init?.body ? JSON.stringify(init.body) : undefined,
    credentials: "include",
    cache: init?.noStore ? "no-store" : "default",
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export function startSession(opening_question?: string) {
  return request<SessionProgressResponse>("/api/v1/chat/session/start", {
    method: "POST",
    body: opening_question ? { opening_question } : {},
  });
}

export function getSession(sessionId: string) {
  return request<SessionStatusResponse>(`/api/v1/chat/session/${sessionId}`, {
    noStore: true,
  });
}

export function answerQuestion(sessionId: string, answer: string | string[]) {
  return request<SessionProgressResponse>(
    `/api/v1/chat/session/${sessionId}/answer`,
    {
      method: "POST",
      body: { answer },
    },
  );
}

export function completeSession(sessionId: string) {
  return request<SessionSummaryResponse>(`/api/v1/chat/session/${sessionId}/complete`, {
    method: "POST",
  });
}

export function sendFollowup(
  sessionId: string,
  question: string,
  clientRequestId: string,
) {
  return request<FollowupResponse>(
    `/api/v1/chat/session/${sessionId}/message`,
    {
      method: "POST",
      body: {
        question,
        client_request_id: clientRequestId,
      },
    },
  );
}

export function getAuthState() {
  return request<AuthState>("/api/v1/auth/me", { noStore: true });
}

export function startEmailVerification(email: string, sessionId: string) {
  return request<EmailStartResponse>("/api/v1/auth/email/start", {
    method: "POST",
    body: { email, session_id: sessionId },
  });
}

export function verifyEmailCode(email: string, code: string, sessionId: string) {
  return request<EmailVerifyResponse>("/api/v1/auth/email/verify", {
    method: "POST",
    body: { email, code, session_id: sessionId },
  });
}

export function createCheckout(sessionId: string) {
  return request<CheckoutResponse>("/api/v1/billing/checkout", {
    method: "POST",
    body: { session_id: sessionId },
  });
}
