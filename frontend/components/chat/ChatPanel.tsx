"use client";

import { Send, Square } from "lucide-react";
import { useRef, useState } from "react";

import type { AskHistoryTurn } from "@/lib/api";
import { streamAsk } from "@/lib/api";
import MessageBubble from "@/components/chat/MessageBubble";
import SuggestedQuestions from "@/components/chat/SuggestedQuestions";
import { useToast } from "@/components/Toast";
import type { ChatMessage, Citation, TraceEvent } from "@/types";

interface ChatPanelProps {
  selectedDocumentIds: string[];
  suggestedQuestions: string[];
  onCitationClick: (citation: Citation) => void;
}

export default function ChatPanel({
  selectedDocumentIds,
  suggestedQuestions,
  onCitationClick,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [isAsking, setIsAsking] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const { showToast } = useToast();

  const updateMessage = (id: string, patch: Partial<ChatMessage> | ((m: ChatMessage) => Partial<ChatMessage>)) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, ...(typeof patch === "function" ? patch(m) : patch) } : m))
    );
  };

  const runQuestion = async (rawQuestion: string) => {
    const trimmed = rawQuestion.trim();
    if (!trimmed || isAsking) return;

    if (selectedDocumentIds.length === 0) {
      showToast("Select at least one document from the library first.");
      return;
    }

    const history: AskHistoryTurn[] = messages
      .filter((m) => !m.error)
      .slice(-6)
      .map((m) => ({ role: m.role, content: m.content }));

    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: "user", content: trimmed };
    const assistantId = crypto.randomUUID();
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      trace: [],
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setQuestion("");
    setIsAsking(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      await streamAsk(
        selectedDocumentIds,
        trimmed,
        history,
        (event) => {
          if (event.type === "trace") {
            const traceEvent: TraceEvent = event.data;
            updateMessage(assistantId, (m) => ({ trace: [...(m.trace ?? []), traceEvent] }));
          } else if (event.type === "token") {
            updateMessage(assistantId, (m) => ({ content: m.content + event.data.text }));
          } else if (event.type === "reset") {
            updateMessage(assistantId, { content: "" });
          } else if (event.type === "final") {
            updateMessage(assistantId, {
              content: event.data.final_answer,
              citations: event.data.citations,
              confidence: event.data.confidence,
              isStreaming: false,
            });
          } else if (event.type === "error") {
            updateMessage(assistantId, { error: event.data.detail, isStreaming: false });
          }
        },
        controller.signal
      );
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        updateMessage(assistantId, (m) => ({ isStreaming: false, error: m.content ? undefined : "Stopped." }));
      } else {
        const message = err instanceof Error ? err.message : "Failed to get an answer.";
        updateMessage(assistantId, { error: message, isStreaming: false });
        showToast(message);
      }
    } finally {
      updateMessage(assistantId, (m) => (m.isStreaming ? { isStreaming: false } : {}));
      setIsAsking(false);
      abortControllerRef.current = null;
    }
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    runQuestion(question);
  };

  const handleStop = () => {
    abortControllerRef.current?.abort();
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="quorum-scroll flex-1 overflow-y-auto px-4 py-4">
        <div className="mx-auto flex max-w-2xl flex-col gap-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center gap-4 py-10 text-center">
              <p className="text-sm text-text-muted">
                {selectedDocumentIds.length === 0
                  ? "Select a document from the library, then ask a question."
                  : "Ask a question about the selected document(s) to get started."}
              </p>
              <SuggestedQuestions questions={suggestedQuestions} onSelect={runQuestion} />
            </div>
          )}

          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} onCitationClick={onCitationClick} />
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="border-t border-border px-4 py-3">
        <div className="mx-auto flex max-w-2xl gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question about the selected document(s)…"
            disabled={isAsking}
            aria-label="Question"
            className="flex-1 rounded-lg border border-border bg-surface px-4 py-2 text-sm text-text placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-from disabled:opacity-60"
          />
          {isAsking ? (
            <button
              type="button"
              onClick={handleStop}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-medium text-text hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-from"
            >
              <Square size={14} />
              Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={!question.trim()}
              aria-label="Send question"
              className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-accent-from to-accent-via px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Send size={14} />
              Send
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
