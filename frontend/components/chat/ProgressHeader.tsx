"use client";

import type { CounselingStage, QuotaState } from "@/lib/types";

const STAGE_LABELS: Record<CounselingStage, string> = {
  intake: "추천 입력",
  ready_for_summary: "추천 준비",
  active_counseling: "추천 결과",
  completed: "세션 종료",
};

interface ProgressHeaderProps {
  stage: CounselingStage;
  answeredCount: number;
  totalQuestions: number;
  quota?: QuotaState | null;
  awaitingAssistant?: boolean;
}

export function ProgressHeader({
  stage,
  answeredCount,
  totalQuestions,
  quota,
  awaitingAssistant = false,
}: ProgressHeaderProps) {
  return (
    <header className="progressHeader">
      <div>
        <div className="progressCount">{STAGE_LABELS[stage]}</div>
      </div>
      <div className="progressMeta">
        {awaitingAssistant ? (
          <span className="progressPill generatingPill">
            <span className="generatingDot" aria-hidden />
            답변 생성 중
          </span>
        ) : null}
        <span className="progressPill">
          intake {answeredCount}/{totalQuestions}
        </span>
        {quota ? (
          <span className="progressPill">
            남은 분석 {quota.remaining}회
          </span>
        ) : null}
      </div>
    </header>
  );
}
