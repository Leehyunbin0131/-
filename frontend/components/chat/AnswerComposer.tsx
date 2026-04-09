"use client";

import { useMemo, useState } from "react";

import type { IntakeQuestion } from "@/lib/types";

interface AnswerComposerProps {
  currentQuestion?: IntakeQuestion | null;
  mode: "intake" | "followup";
  disabled?: boolean;
  onSubmit: (value: string | string[]) => Promise<void> | void;
}

export function AnswerComposer({
  currentQuestion,
  mode,
  disabled = false,
  onSubmit,
}: AnswerComposerProps) {
  const [textValue, setTextValue] = useState("");
  const [selectedValues, setSelectedValues] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const isMultiSelect = Boolean(currentQuestion?.allows_multiple);
  const options = currentQuestion?.options ?? [];
  const canUseOptions = options.length > 0;

  const buttonLabel = useMemo(() => {
    if (submitting) return "전송 중...";
    return mode === "intake" ? "다음으로" : "보내기";
  }, [mode, submitting]);

  async function handleSubmit() {
    if (disabled || submitting) return;

    const payload =
      canUseOptions && selectedValues.length > 0
        ? isMultiSelect
          ? selectedValues
          : selectedValues[0]
        : textValue;

    const hasValue = Array.isArray(payload)
      ? payload.some((item) => item.trim())
      : payload.trim();

    if (!hasValue) return;

    setSubmitting(true);
    try {
      await onSubmit(payload);
      setTextValue("");
      setSelectedValues([]);
    } finally {
      setSubmitting(false);
    }
  }

  function toggleOption(option: string) {
    if (!isMultiSelect) {
      setSelectedValues([option]);
      return;
    }
    setSelectedValues((current) =>
      current.includes(option)
        ? current.filter((item) => item !== option)
        : [...current, option],
    );
  }

  const busy = disabled || submitting;

  return (
    <div className="composerShell">
      <div className={`composerBox${busy ? " composerBoxBusy" : ""}`}>
        <div className="composerLabel">
          {currentQuestion?.help_text ??
            (mode === "intake"
              ? "모르면 '아직 모르겠음'이라고 적어도 됩니다."
              : "추천 결과를 바탕으로 더 좁히거나 생활 조건을 물어볼 수 있어요.")}
        </div>

        {canUseOptions ? (
          <div className="optionGrid">
            {options.map((option) => {
              const selected = selectedValues.includes(option);
              return (
                <button
                  key={option}
                  className="optionButton"
                  style={{
                    borderColor: selected ? "#111111" : undefined,
                    background: selected ? "#111111" : undefined,
                    color: selected ? "#ffffff" : undefined,
                  }}
                  type="button"
                  onClick={() => toggleOption(option)}
                  disabled={busy}
                >
                  {option}
                </button>
              );
            })}
          </div>
        ) : null}

        <textarea
          className="composerTextarea"
          placeholder={
            currentQuestion?.placeholder ??
            (mode === "intake"
              ? "답변을 입력하세요."
              : "추가로 비교하거나 확인하고 싶은 점을 적어주세요.")
          }
          value={textValue}
          onChange={(event) => setTextValue(event.target.value)}
          disabled={busy}
        />

        <div className="composerActions">
          <div className="composerHint">
            {busy
              ? mode === "followup"
                ? "상담사가 답변을 준비하는 동안 잠시만 기다려 주세요."
                : "다음 내용을 준비하는 동안 잠시만 기다려 주세요."
              : mode === "intake"
                ? "지금 단계에서는 입시 추천에 필요한 입력만 짧게 확인합니다."
                : "후속 질문은 대학 비교, 전형 비교, 기숙사/등록금 확인에 활용할 수 있습니다."}
          </div>
          <button
            type="button"
            className={`primaryButton${submitting ? " primaryButtonPulse" : ""}`}
            onClick={handleSubmit}
            disabled={busy}
          >
            {buttonLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
