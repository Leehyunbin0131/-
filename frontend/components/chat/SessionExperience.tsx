"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  answerQuestion,
  completeSession,
  createCheckout,
  getSession,
  sendFollowup,
  startEmailVerification,
  verifyEmailCode,
} from "@/lib/api";
import { AnswerComposer } from "@/components/chat/AnswerComposer";
import { ConversationPane } from "@/components/chat/ConversationPane";
import { ProgressHeader } from "@/components/chat/ProgressHeader";
import { PaywallSheet } from "@/components/paywall/PaywallSheet";
import type {
  SessionStatusResponse,
  SessionSummaryResponse,
} from "@/lib/types";

interface SessionExperienceProps {
  sessionId: string;
}

export function SessionExperience({ sessionId }: SessionExperienceProps) {
  const [status, setStatus] = useState<SessionStatusResponse | null>(null);
  const [summary, setSummary] = useState<SessionSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [paywallOpen, setPaywallOpen] = useState(false);
  const [verificationCode, setVerificationCode] = useState<string | null>(null);
  const autoCompleted = useRef(false);

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

  const conversation = useMemo(
    () => summary?.conversation ?? status?.session.conversation ?? [],
    [status, summary],
  );
  const quota = summary?.quota ?? status?.quota ?? null;

  async function handleIntakeSubmit(value: string | string[]) {
    setActionLoading(true);
    setError(null);
    try {
      const progress = await answerQuestion(sessionId, value);
      setStatus((current) =>
        current
          ? {
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
            }
          : null,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "답변을 저장하지 못했습니다.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleComplete() {
    setActionLoading(true);
    setError(null);
    try {
      const result = await completeSession(sessionId);
      setSummary(result);
      setStatus((current) =>
        current
          ? {
              ...current,
              session: {
                ...current.session,
                stage: result.stage,
                final_summary: result.summary,
                conversation: result.conversation,
              },
              quota: result.quota,
            }
          : current,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "상담 요약을 생성하지 못했습니다.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleFollowupSubmit(value: string | string[]) {
    if (Array.isArray(value)) return;
    setActionLoading(true);
    setError(null);
    try {
      const result = await sendFollowup(
        sessionId,
        value,
        crypto.randomUUID(),
      );
      setSummary((current) =>
        current
          ? {
              ...current,
              stage: result.stage,
              conversation: result.conversation,
              quota: result.quota,
            }
          : current,
      );
      if (result.quota.requires_upgrade || result.stage === "upgrade_required") {
        setPaywallOpen(true);
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "후속 상담을 진행하지 못했습니다.";
      setError(message);
      if (message.toLowerCase().includes("upgrade")) {
        setPaywallOpen(true);
      }
    } finally {
      setActionLoading(false);
    }
  }

  async function handleSendCode(email: string) {
    const result = await startEmailVerification(email, sessionId);
    setVerificationCode(result.verification_code ?? null);
    return result.verification_code ?? undefined;
  }

  async function handleVerify(email: string, code: string) {
    await verifyEmailCode(email, code, sessionId);
  }

  async function handleCheckout() {
    const result = await createCheckout(sessionId);
    window.location.href = result.checkout_url;
  }

  if (loading) {
    return (
      <div className="chatShell">
        <div className="chatColumn">
          <div className="statusBanner">상담 세션을 불러오는 중입니다...</div>
        </div>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="chatShell">
        <div className="chatColumn">
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
    );
  }

  const isIntake = status.session.stage === "intake";
  const showFollowup = Boolean(summary);

  return (
    <div className="chatShell">
      <div className="chatColumn">
        <ProgressHeader
          stage={summary?.stage ?? status.session.stage}
          answeredCount={status.answered_count}
          totalQuestions={status.total_questions}
          quota={quota}
        />

        {error ? <div className="statusBanner">{error}</div> : null}

        {!isIntake && !summary ? (
          <div className="statusBanner">상담 요약을 준비하고 있습니다...</div>
        ) : null}

        <ConversationPane
          conversation={conversation}
          summary={summary?.summary}
          evidence={summary?.evidence}
        />

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
            disabled={actionLoading || Boolean(quota?.requires_upgrade)}
            onSubmit={handleFollowupSubmit}
          />
        ) : null}

        {quota?.requires_upgrade ? (
          <div className="statusBanner">
            무료 체험 상담 횟수를 모두 사용했습니다. 결제 후 같은 맥락으로 계속
            이어갈 수 있어요.
          </div>
        ) : null}
      </div>

      <PaywallSheet
        open={paywallOpen || Boolean(quota?.requires_upgrade)}
        sessionId={sessionId}
        verificationCode={verificationCode}
        loading={actionLoading}
        onClose={() => setPaywallOpen(false)}
        onSendCode={handleSendCode}
        onVerify={handleVerify}
        onCheckout={handleCheckout}
      />
    </div>
  );
}
