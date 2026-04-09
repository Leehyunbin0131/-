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

  return (
    <div className="composerShell">
      <div className="composerBox">
        <div className="composerLabel">
          {currentQuestion?.help_text ??
            (mode === "intake"
              ? "짧게 적어도 괜찮습니다."
              : "후속 질문을 자유롭게 적어보세요.")}
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
                  disabled={disabled || submitting}
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
            mode === "intake"
              ? "답변을 입력하세요."
              : "추가로 상담받고 싶은 점을 적어주세요."
          }
          value={textValue}
          onChange={(event) => setTextValue(event.target.value)}
          disabled={disabled || submitting}
        />

        <div className="composerActions">
          <div className="composerHint">
            {mode === "intake"
              ? "지금 단계에서는 상황 파악 질문을 진행합니다."
              : "후속 상담은 남은 턴 수만큼 이어갈 수 있습니다."}
          </div>
          <button
            type="button"
            className="primaryButton"
            onClick={handleSubmit}
            disabled={disabled || submitting}
          >
            {buttonLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
