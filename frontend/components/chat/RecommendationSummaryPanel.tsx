"use client";

import type { CounselingSummary } from "@/lib/types";

interface RecommendationSummaryPanelProps {
  summary: CounselingSummary;
}

export function RecommendationSummaryPanel({
  summary,
}: RecommendationSummaryPanelProps) {
  return (
    <section className="conversationPane" style={{ paddingTop: 0 }}>
      <div className="messageRow assistant">
        <div className="messageBubble">
          <div className="messageMeta">추천 요약</div>
          <div className="messagePlain">{summary.overview}</div>
        </div>
      </div>

      {summary.recommended_options.map((option, index) => (
        <div
          key={`recommended-option-${index}-${option.university}-${option.major}-${option.track}`}
          className="messageRow assistant"
        >
          <div className="messageBubble">
            <div className="messageMeta">추천 조합</div>
            <div className="messagePlain">
              <strong>
                {option.university} / {option.major} / {option.track}
              </strong>
            </div>
            <div className="messagePlain" style={{ marginTop: 10 }}>
              {option.fit_reason}
            </div>
            <div className="messagePlain" style={{ marginTop: 10 }}>
              {option.evidence_summary}
            </div>
            {option.metrics_line ? (
              <div className="messagePlain" style={{ marginTop: 10 }}>
                <strong>모집결과 수치</strong>: {option.metrics_line}
              </div>
            ) : null}
            {option.source_file_hint ? (
              <div className="messagePlain" style={{ marginTop: 10 }}>
                <strong>근거 파일</strong>: {option.source_file_hint}
              </div>
            ) : null}
            {option.dorm_note ? (
              <div className="messagePlain" style={{ marginTop: 10 }}>
                기숙사: {option.dorm_note}
              </div>
            ) : null}
            {option.tuition_note ? (
              <div className="messagePlain" style={{ marginTop: 10 }}>
                등록금: {option.tuition_note}
              </div>
            ) : null}
            {option.next_step ? (
              <div className="messagePlain" style={{ marginTop: 10 }}>
                다음 단계: {option.next_step}
              </div>
            ) : null}
          </div>
        </div>
      ))}

      {summary.next_actions.length ? (
        <div className="messageRow assistant">
          <div className="messageBubble">
            <div className="messageMeta">다음 액션</div>
            <div className="messagePlain" style={{ whiteSpace: "pre-line" }}>
              {summary.next_actions.map((item) => `- ${item}`).join("\n")}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
