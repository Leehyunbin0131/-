"use client";

import type { CounselingStage, QuotaState } from "@/lib/types";

const STAGE_LABELS: Record<CounselingStage, string> = {
  intake: "상황 파악",
  ready_for_summary: "요약 준비",
  active_counseling: "상담 진행",
  upgrade_required: "업그레이드 필요",
  completed: "상담 완료",
};

interface ProgressHeaderProps {
  stage: CounselingStage;
  answeredCount: number;
  totalQuestions: number;
  quota?: QuotaState | null;
}

export function ProgressHeader({
  stage,
  answeredCount,
  totalQuestions,
  quota,
}: ProgressHeaderProps) {
  return (
    <header className="progressHeader">
      <div>
        <div className="progressCount">{STAGE_LABELS[stage]}</div>
      </div>
      <div className="progressMeta">
        <span className="progressPill">
          intake {answeredCount}/{totalQuestions}
        </span>
        {quota ? (
          <span className="progressPill">
            남은 상담 {quota.total_remaining}회
          </span>
        ) : null}
        {quota ? (
          <span className="progressPill">
            {quota.actor_type === "guest" ? "체험 중" : "결제 계정"}
          </span>
        ) : null}
      </div>
    </header>
  );
}
