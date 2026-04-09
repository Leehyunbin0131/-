"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  answerQuestion,
  completeSession,
  getSession,
  sendFollowup,
} from "@/lib/api";
import { AnswerComposer } from "@/components/chat/AnswerComposer";
import { ConversationPane } from "@/components/chat/ConversationPane";
import { ProgressHeader } from "@/components/chat/ProgressHeader";
import { RecommendationSummaryPanel } from "@/components/chat/RecommendationSummaryPanel";
import type {
  FollowupResponse,
  SessionProgressResponse,
  SessionStatusResponse,
  SessionSummaryResponse,
} from "@/lib/types";

interface SessionExperienceProps {
  sessionId: string;
}

const SUMMARY_POLL_INTERVAL_MS = 1500;
const SUMMARY_POLL_TIMEOUT_MS = 10 * 60 * 1000;
const DEFAULT_SUMMARY_WAIT_MESSAGE =
  "상담 요약을 준비하고 있습니다. 자료량에 따라 약 5분 정도 소요될 수 있습니다.";
const DEFAULT_FOLLOWUP_WAIT_MESSAGE =
  "후속 답변을 준비하고 있습니다. 자료량에 따라 약 5분 정도 소요될 수 있습니다.";
const SUMMARY_TIMEOUT_MESSAGE =
  "추천 요약이 예상보다 오래 걸립니다. 자료량에 따라 5분 이상 걸릴 수 있습니다. 잠시 후 페이지를 새로고침한 뒤 다시 시도해 주세요.";
const FOLLOWUP_TIMEOUT_MESSAGE =
  "후속 답변이 예상보다 오래 걸립니다. 잠시 후 페이지를 새로고침한 뒤 다시 시도해 주세요.";

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

function normalizeSummaryNotice(message?: string | null) {
  const trimmed = message?.trim();
  return trimmed || DEFAULT_SUMMARY_WAIT_MESSAGE;
}

function mergeProgressIntoStatus(
  current: SessionStatusResponse | null,
  progress: SessionProgressResponse,
): SessionStatusResponse | null {
  if (!current) {
    return null;
  }
  return {
    ...current,
    session: {
      ...current.session,
      stage: progress.stage,
      user_profile: progress.user_profile,
      conversation: progress.conversation,
    },
    current_question: progress.current_question ?? null,
    answered_count: progress.answered_count,
    total_questions: progress.total_questions,
    can_complete: progress.can_complete,
    quota: progress.quota,
  };
}

function mergeSummaryIntoStatus(
  current: SessionStatusResponse | null,
  result: SessionSummaryResponse,
): SessionStatusResponse | null {
  if (!current) {
    return current;
  }
  return {
    ...current,
    session: {
      ...current.session,
      stage: result.stage,
      final_summary: result.summary,
      conversation: result.conversation,
      summary_job_status: "none",
      summary_job_error: null,
    },
    quota: result.quota,
  };
}

function mergeFollowupIntoSummary(
  current: SessionSummaryResponse | null,
  result: FollowupResponse,
): SessionSummaryResponse | null {
  if (!current) {
    return current;
  }
  return {
    ...current,
    stage: result.stage,
    conversation: result.conversation,
    quota: result.quota,
  };
}

function conversationHasFollowupAnswer(
  st: SessionStatusResponse,
  clientRequestId: string,
) {
  return st.session.conversation.some(
    (message) =>
      message.kind === "followup_answer" && message.request_id === clientRequestId,
  );
}

export function SessionExperience({ sessionId }: SessionExperienceProps) {
  const [status, setStatus] = useState<SessionStatusResponse | null>(null);
  const [summary, setSummary] = useState<SessionSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summaryNotice, setSummaryNotice] = useState<string | null>(null);
  const [followupNotice, setFollowupNotice] = useState<string | null>(null);
  const autoCompleted = useRef(false);
  const conversationScrollTargetRef = useRef<HTMLDivElement>(null);

  async function loadStatus() {
    setLoading(true);
    setError(null);
    try {
      const result = await getSession(sessionId);
      setStatus(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "상담 세션을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadStatus();
  }, [sessionId]);

  useEffect(() => {
    const shouldLoadSummary =
      status?.session.final_summary ||
      status?.session.stage === "ready_for_summary";
    if (shouldLoadSummary && !summary && !autoCompleted.current) {
      autoCompleted.current = true;
      void handleComplete();
    }
  }, [status, summary]);

  const conversation = useMemo(() => {
    const source = summary?.conversation ?? status?.session.conversation ?? [];
    if (!summary) {
      return source;
    }
    return source.filter(
      (message) =>
        message.kind === "followup_question" ||
        message.kind === "followup_answer" ||
        message.kind === "opening_question",
    );
  }, [status, summary]);
  const quota = summary?.quota ?? status?.quota ?? null;

  const lastMessageId = conversation.at(-1)?.message_id;

  useEffect(() => {
    const id = requestAnimationFrame(() => {
      const el = conversationScrollTargetRef.current;
      if (!el) return;
      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      el.scrollIntoView({
        behavior: reduced ? "auto" : "smooth",
        block: "start",
      });
    });
    return () => cancelAnimationFrame(id);
  }, [lastMessageId, summary, actionLoading, error]);

  async function handleIntakeSubmit(value: string | string[]) {
    setActionLoading(true);
    setError(null);
    try {
      const progress = await answerQuestion(sessionId, value);
      setStatus((current) => mergeProgressIntoStatus(current, progress));
    } catch (err) {
      setError(err instanceof Error ? err.message : "답변을 저장하지 못했습니다.");
    } finally {
      setActionLoading(false);
    }
  }

  function applySummaryResult(result: SessionSummaryResponse) {
    setSummary(result);
    setSummaryNotice(null);
    setStatus((current) => mergeSummaryIntoStatus(current, result));
  }

  async function waitForSummaryResult() {
    const pollDeadline = Date.now() + SUMMARY_POLL_TIMEOUT_MS;
    while (Date.now() < pollDeadline) {
      await sleep(SUMMARY_POLL_INTERVAL_MS);
      const nextStatus = await getSession(sessionId);
      setStatus(nextStatus);

      if (nextStatus.session.summary_job_status === "failed") {
        throw new Error(
          nextStatus.session.summary_job_error?.trim() ||
            "추천 요약 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.",
        );
      }
      if (!nextStatus.session.final_summary) {
        continue;
      }

      const completed = await completeSession(sessionId);
      if (completed.kind === "complete") {
        return completed.data;
      }
      throw new Error(
        "요약이 준비된 것으로 보이나 전체 응답을 받지 못했습니다. 새로고침해 주세요.",
      );
    }

    throw new Error(SUMMARY_TIMEOUT_MESSAGE);
  }

  async function waitForFollowupResult(clientRequestId: string) {
    const pollDeadline = Date.now() + SUMMARY_POLL_TIMEOUT_MS;
    while (Date.now() < pollDeadline) {
      await sleep(SUMMARY_POLL_INTERVAL_MS);
      const nextStatus = await getSession(sessionId);
      setStatus(nextStatus);
      if (nextStatus.session.followup_job_status === "failed") {
        throw new Error(
          nextStatus.session.followup_job_error?.trim() ||
            "후속 답변 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.",
        );
      }
      const idle = nextStatus.session.followup_job_status === "none";
      if (idle && conversationHasFollowupAnswer(nextStatus, clientRequestId)) {
        return;
      }
    }
    throw new Error(FOLLOWUP_TIMEOUT_MESSAGE);
  }

  async function handleComplete() {
    setActionLoading(true);
    setError(null);
    setSummaryNotice(DEFAULT_SUMMARY_WAIT_MESSAGE);
    try {
      const first = await completeSession(sessionId);
      if (first.kind === "complete") {
        applySummaryResult(first.data);
        return;
      }

      setSummaryNotice(normalizeSummaryNotice(first.data.message));
      const result = await waitForSummaryResult();
      applySummaryResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "상담 요약을 생성하지 못했습니다.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleFollowupSubmit(value: string | string[]) {
    if (Array.isArray(value)) return;
    const clientRequestId = crypto.randomUUID();
    setActionLoading(true);
    setError(null);
    setFollowupNotice(DEFAULT_FOLLOWUP_WAIT_MESSAGE);
    try {
      const first = await sendFollowup(sessionId, value, clientRequestId);
      if (first.kind === "complete") {
        setFollowupNotice(null);
        setSummary((current) => mergeFollowupIntoSummary(current, first.data));
        return;
      }
      setFollowupNotice(
        first.data.message?.trim() || DEFAULT_FOLLOWUP_WAIT_MESSAGE,
      );
      await waitForFollowupResult(clientRequestId);
      const again = await sendFollowup(sessionId, value, clientRequestId);
      if (again.kind === "complete") {
        setFollowupNotice(null);
        setSummary((current) => mergeFollowupIntoSummary(current, again.data));
      } else {
        setError(
          "답변이 준비된 것으로 보이나 전체 응답을 받지 못했습니다. 새로고침해 주세요.",
        );
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "후속 상담을 진행하지 못했습니다.";
      setError(message);
    } finally {
      setFollowupNotice(null);
      setActionLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="chatShell">
        <div className="chatColumn">
          <div className="chatScrollRegion">
            <div className="statusBanner">상담 세션을 불러오는 중입니다...</div>
          </div>
        </div>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="chatShell">
        <div className="chatColumn">
          <div className="chatScrollRegion">
            <div className="statusBanner">
              상담 세션을 찾지 못했습니다. 다시 체험을 시작해주세요.
            </div>
            {error ? (
              <div className="statusBanner" style={{ marginTop: 12 }}>
                {error}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  const isIntake = status.session.stage === "intake";
  const showFollowup = Boolean(summary);
  const summaryPendingMessage =
    !isIntake && !summary && !error ? normalizeSummaryNotice(summaryNotice) : null;
  const followupPendingMessage =
    showFollowup && followupNotice && !error ? followupNotice : null;

  return (
    <div className="chatShell">
      <div className="chatColumn">
        <div className="chatScrollRegion">
          <ProgressHeader
            stage={summary?.stage ?? status.session.stage}
            answeredCount={status.answered_count}
            totalQuestions={status.total_questions}
            quota={quota}
            awaitingAssistant={actionLoading}
          />

          {error ? <div className="statusBanner">{error}</div> : null}

          {summary ? <RecommendationSummaryPanel summary={summary.summary} /> : null}

          <ConversationPane
            conversation={conversation}
            awaitingAssistant={actionLoading}
            scrollTargetRef={conversationScrollTargetRef}
          />
        </div>

        <div className="chatComposerDock">
          {isIntake && status.current_question ? (
            <AnswerComposer
              currentQuestion={status.current_question}
              mode="intake"
              disabled={actionLoading}
              onSubmit={handleIntakeSubmit}
            />
          ) : null}

          {showFollowup ? (
            <AnswerComposer
              mode="followup"
              disabled={actionLoading || Boolean(quota?.exhausted)}
              onSubmit={handleFollowupSubmit}
            />
          ) : null}

          {followupPendingMessage ? (
            <div className="statusBanner">{followupPendingMessage}</div>
          ) : null}

          {summaryPendingMessage ? (
            <div className="statusBanner">{summaryPendingMessage}</div>
          ) : null}

          {quota?.exhausted ? (
            <div className="statusBanner">
              무료 추천 분석 횟수를 모두 사용했습니다. 같은 세션 내용은 그대로
              남아 있으니, 새 입력을 시작할 때 참고하실 수 있습니다.
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
