"use client";

import { useState } from "react";

interface PaywallSheetProps {
  open: boolean;
  sessionId: string;
  verificationCode?: string | null;
  loading?: boolean;
  onClose: () => void;
  onSendCode: (email: string) => Promise<string | undefined>;
  onVerify: (email: string, code: string) => Promise<void>;
  onCheckout: () => Promise<void>;
}

export function PaywallSheet({
  open,
  sessionId,
  verificationCode,
  loading = false,
  onClose,
  onSendCode,
  onVerify,
  onCheckout,
}: PaywallSheetProps) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [localCode, setLocalCode] = useState<string | null>(verificationCode ?? null);
  const [verified, setVerified] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  if (!open) return null;

  async function handleSendCode() {
    setSubmitting(true);
    setMessage(null);
    try {
      const returnedCode = await onSendCode(email);
      if (returnedCode) {
        setLocalCode(returnedCode);
        setMessage(`개발 모드 인증코드: ${returnedCode}`);
      } else {
        setMessage("인증 코드를 보냈습니다.");
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "인증 코드를 보내지 못했습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleVerify() {
    setSubmitting(true);
    setMessage(null);
    try {
      await onVerify(email, code);
      setVerified(true);
      setMessage("이메일 확인이 완료되었습니다. 이제 결제를 진행할 수 있어요.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "이메일 확인에 실패했습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCheckout() {
    setSubmitting(true);
    setMessage(null);
    try {
      await onCheckout();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "결제를 시작하지 못했습니다.");
      setSubmitting(false);
    }
  }

  return (
    <div className="paywallOverlay">
      <div className="paywallSheet">
        <h2 className="paywallTitle">상담을 계속 이어가려면</h2>
        <p className="paywallBody">
          지금까지의 상담 맥락은 그대로 유지됩니다. $1.99를 결제하면 추가
          30회 상담을 이어갈 수 있습니다.
        </p>
        <ul className="paywallList">
          <li>현재 상담 흐름과 요약을 그대로 유지합니다.</li>
          <li>추가 30턴을 일회성으로 받습니다.</li>
          <li>계정은 결제 직전에만 간단히 인증합니다.</li>
        </ul>
        <div className="paywallPrice">
          <strong>$1.99</strong> 일회성 결제 / 30회 추가 상담
        </div>
        <input
          className="paywallField"
          type="email"
          value={email}
          placeholder="결제 전에 사용할 이메일"
          onChange={(event) => setEmail(event.target.value)}
          disabled={submitting || loading}
        />
        <div className="inlineRow">
          <button
            type="button"
            className="secondaryButton"
            onClick={handleSendCode}
            disabled={!email || submitting || loading}
          >
            인증 코드 받기
          </button>
          <button
            type="button"
            className="secondaryButton"
            onClick={onClose}
            disabled={submitting || loading}
          >
            나중에 할게요
          </button>
        </div>

        <input
          className="paywallField"
          type="text"
          value={code}
          placeholder="인증 코드 입력"
          onChange={(event) => setCode(event.target.value)}
          disabled={submitting || loading}
        />
        <div className="inlineRow">
          <button
            type="button"
            className="secondaryButton"
            onClick={handleVerify}
            disabled={!email || !code || submitting || loading}
          >
            이메일 확인
          </button>
          <button
            type="button"
            className="primaryButton"
            onClick={handleCheckout}
            disabled={!verified || submitting || loading}
          >
            결제하고 계속 상담하기
          </button>
        </div>

        <div className="mutedText" style={{ marginTop: 12 }}>
          session: {sessionId}
        </div>
        {localCode ? (
          <div className="mutedText" style={{ marginTop: 6 }}>
            개발 모드 코드: {localCode}
          </div>
        ) : null}
        {message ? (
          <div className="statusBanner" style={{ marginTop: 12 }}>
            {message}
          </div>
        ) : null}
      </div>
    </div>
  );
}
