"use client";

import type {
  ConversationMessage,
  CounselingSummary,
  EvidenceItem,
} from "@/lib/types";

interface ConversationPaneProps {
  conversation: ConversationMessage[];
  summary?: CounselingSummary | null;
  evidence?: EvidenceItem[];
}

export function ConversationPane({
  conversation,
  summary,
  evidence = [],
}: ConversationPaneProps) {
  return (
    <section className="conversationPane">
      {conversation.map((message) => (
        <div
          key={message.message_id}
          className={`messageRow ${message.role === "assistant" ? "assistant" : "user"}`}
        >
          <div className="messageBubble">
            <div className="messageMeta">
              {message.role === "assistant" ? "상담사" : "나"}
            </div>
            {message.content}
          </div>
        </div>
      ))}

      {summary ? (
        <>
          <div className="summarySection">
            <div className="summaryTitle">상황 요약</div>
            <div>{summary.situation_summary}</div>
          </div>

          <div className="summarySection">
            <div className="summaryTitle">추천 방향</div>
            {summary.recommended_directions.map((direction) => (
              <div key={direction.title} style={{ marginBottom: 18 }}>
                <h3 className="summaryBlockTitle">{direction.title}</h3>
                <div>{direction.fit_reason}</div>
                <div className="mutedText" style={{ marginTop: 8 }}>
                  근거: {direction.evidence_summary}
                </div>
                {direction.action_tip ? (
                  <div className="mutedText" style={{ marginTop: 8 }}>
                    다음: {direction.action_tip}
                  </div>
                ) : null}
              </div>
            ))}
          </div>

          <div className="summarySection">
            <div className="summaryTitle">리스크와 현실적 체크포인트</div>
            <ul className="simpleList">
              {summary.risks_and_tradeoffs.map((item) => (
                <li key={`${item.direction_title}-${item.risk}`}>
                  <strong>{item.direction_title}</strong>: {item.risk} /{" "}
                  {item.reality_check}
                </li>
              ))}
            </ul>
          </div>

          <div className="summarySection">
            <div className="summaryTitle">다음 행동</div>
            <ul className="simpleList">
              {summary.next_actions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>

          {evidence.length > 0 ? (
            <div className="summarySection">
              <div className="summaryTitle">통계 근거</div>
              <ul className="simpleList">
                {evidence.map((item) => (
                  <li key={item.table_id}>
                    {item.table_title}
                    {item.snapshot_date ? ` (${item.snapshot_date})` : ""}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
