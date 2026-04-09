"use client";

import type { RefObject } from "react";

import { AssistantMessageMarkdown } from "@/components/chat/AssistantMessageMarkdown";
import type { ConversationMessage } from "@/lib/types";

interface ConversationPaneProps {
  conversation: ConversationMessage[];
  awaitingAssistant?: boolean;
  /** Scroll target: typing row while waiting, else last message — aligned with block:start + scroll-margin */
  scrollTargetRef?: RefObject<HTMLDivElement | null>;
}

function TypingIndicator() {
  return (
    <div className="messageRow assistant messageRowAnimated">
      <div
        className="messageBubble typingBubble"
        aria-busy="true"
        aria-live="polite"
        aria-label="추천 결과를 정리 중입니다"
      >
        <div className="messageMeta">추천 엔진</div>
        <div className="typingDots">
          <span />
          <span />
          <span />
        </div>
      </div>
    </div>
  );
}

export function ConversationPane({
  conversation,
  awaitingAssistant = false,
  scrollTargetRef,
}: ConversationPaneProps) {
  const lastIndex = conversation.length - 1;
  const refOnLastMessage =
    Boolean(scrollTargetRef) && !awaitingAssistant && conversation.length > 0;
  const refOnTyping = Boolean(scrollTargetRef) && awaitingAssistant;

  return (
    <section className="conversationPane">
      {conversation.map((message, index) => (
        <div
          key={message.message_id}
          ref={refOnLastMessage && index === lastIndex ? scrollTargetRef : undefined}
          className={`messageRow ${message.role === "assistant" ? "assistant" : "user"} messageRowAnimated${refOnLastMessage && index === lastIndex ? " conversationScrollTarget" : ""}`}
        >
          <div className="messageBubble">
            <div className="messageMeta">
              {message.role === "assistant" ? "추천 엔진" : "나"}
            </div>
            {message.role === "assistant" ? (
              <AssistantMessageMarkdown content={message.content} />
            ) : (
              <div className="messagePlain">{message.content}</div>
            )}
          </div>
        </div>
      ))}

      {awaitingAssistant ? (
        <div
          ref={refOnTyping ? scrollTargetRef : undefined}
          className={refOnTyping ? "conversationScrollTarget" : undefined}
        >
          <TypingIndicator />
        </div>
      ) : null}
    </section>
  );
}
