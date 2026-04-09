"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface AssistantMessageMarkdownProps {
  content: string;
}

export function AssistantMessageMarkdown({ content }: AssistantMessageMarkdownProps) {
  return (
    <div className="messageMarkdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a href={href ?? "#"} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
