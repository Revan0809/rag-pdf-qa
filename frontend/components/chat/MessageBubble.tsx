"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import CitationChip from "@/components/chat/CitationChip";
import ConfidenceBadge from "@/components/chat/ConfidenceBadge";
import AgentTrace from "@/components/trace/AgentTrace";
import type { ChatMessage, Citation } from "@/types";

interface MessageBubbleProps {
  message: ChatMessage;
  onCitationClick: (citation: Citation) => void;
}

export default function MessageBubble({ message, onCitationClick }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API unavailable; a failed copy of a non-critical
      // convenience action isn't worth an error toast.
    }
  };

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-gradient-to-br from-accent-from to-accent-via px-4 py-2 text-sm text-white shadow-sm">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="flex max-w-[90%] flex-col gap-2 rounded-2xl border border-border bg-surface px-4 py-3 text-sm shadow-sm">
        {message.error ? (
          <p className="text-danger">{message.error}</p>
        ) : (
          <div className="prose prose-sm max-w-none text-text prose-headings:text-text prose-strong:text-text prose-a:text-accent-from prose-code:text-text prose-pre:bg-bg">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content || "…"}</ReactMarkdown>
          </div>
        )}

        {message.citations && message.citations.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {message.citations.map((citation, index) => (
              <CitationChip
                key={`${citation.doc_id}-${citation.page}-${index}`}
                citation={citation}
                onClick={onCitationClick}
              />
            ))}
          </div>
        )}

        {message.confidence && (
          <div className="flex items-center justify-between gap-2">
            <ConfidenceBadge confidence={message.confidence} />
            {!message.isStreaming && message.content && (
              <button
                type="button"
                onClick={handleCopy}
                aria-label="Copy answer"
                className="inline-flex items-center gap-1 rounded text-xs text-text-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-from"
              >
                {copied ? <Check size={12} /> : <Copy size={12} />}
                {copied ? "Copied" : "Copy"}
              </button>
            )}
          </div>
        )}

        {(message.trace && message.trace.length > 0) || message.isStreaming ? (
          <AgentTrace events={message.trace ?? []} isStreaming={!!message.isStreaming} />
        ) : null}
      </div>
    </div>
  );
}
