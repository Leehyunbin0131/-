import type {
  CompleteSessionAcceptedResponse,
  FollowupAcceptedResponse,
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

function httpErrorMessage(body: string, status: number): string {
  const trimmed = body.trim();
  if (!trimmed) {
    return `Request failed (${status})`;
  }
  try {
    const data = JSON.parse(trimmed) as { detail?: unknown };
    if (typeof data.detail === "string") {
      return data.detail;
    }
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((item) =>
          typeof item === "object" && item !== null && "msg" in item
            ? String((item as { msg: string }).msg)
            : String(item),
        )
        .join(" ");
    }
  } catch {
    /* plain text body */
  }
  return trimmed;
}

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
    throw new Error(httpErrorMessage(text, response.status));
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

export type CompleteSessionOutcome =
  | { kind: "complete"; data: SessionSummaryResponse }
  | { kind: "accepted"; data: CompleteSessionAcceptedResponse };

export async function completeSession(
  sessionId: string,
): Promise<CompleteSessionOutcome> {
  const url = `${API_BASE_URL}/api/v1/chat/session/${sessionId}/complete`;
  const response = await fetch(url, {
    method: "POST",
    credentials: "include",
  });
  const text = await response.text();
  if (response.status === 200) {
    return {
      kind: "complete",
      data: JSON.parse(text) as SessionSummaryResponse,
    };
  }
  if (response.status === 202) {
    return {
      kind: "accepted",
      data: JSON.parse(text) as CompleteSessionAcceptedResponse,
    };
  }
  if (!response.ok) {
    throw new Error(httpErrorMessage(text, response.status));
  }
  throw new Error(`Unexpected status ${response.status}`);
}

export type SendFollowupOutcome =
  | { kind: "complete"; data: FollowupResponse }
  | { kind: "accepted"; data: FollowupAcceptedResponse };

export async function sendFollowup(
  sessionId: string,
  question: string,
  clientRequestId: string,
): Promise<SendFollowupOutcome> {
  const url = `${API_BASE_URL}/api/v1/chat/session/${sessionId}/message`;
  const response = await fetch(url, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      client_request_id: clientRequestId,
    }),
  });
  const text = await response.text();
  if (response.status === 200) {
    return {
      kind: "complete",
      data: JSON.parse(text) as FollowupResponse,
    };
  }
  if (response.status === 202) {
    return {
      kind: "accepted",
      data: JSON.parse(text) as FollowupAcceptedResponse,
    };
  }
  if (!response.ok) {
    throw new Error(httpErrorMessage(text, response.status));
  }
  throw new Error(`Unexpected status ${response.status}`);
}
