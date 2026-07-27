"use client";

import { useState } from "react";

import { askQuestion } from "@/lib/api";
import type { ChatMessage } from "@/types";

interface ChatPanelProps {
  documentId: string;
}

export default function ChatPanel({ documentId }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [isAsking, setIsAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || isAsking) return;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
    };
    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");
    setError(null);
    setIsAsking(true);

    try {
      const result = await askQuestion(documentId, trimmed);
      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: result.answer,
        sourcePages: result.source_pages,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get an answer.");
    } finally {
      setIsAsking(false);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto flex flex-col gap-4">
      <div className="flex flex-col gap-3 min-h-[200px]">
        {messages.length === 0 && (
          <p className="text-center text-gray-400 text-sm py-8">
            Ask a question about the document to get started.
          </p>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap shadow-sm ${
                message.role === "user"
                  ? "bg-gradient-to-br from-indigo-600 to-purple-600 text-white"
                  : "bg-white text-gray-900 border border-indigo-100"
              }`}
            >
              <p>{message.content}</p>
              {message.sourcePages && message.sourcePages.length > 0 && (
                <div className="flex gap-1.5 mt-2 flex-wrap">
                  {message.sourcePages.map((page) => (
                    <span
                      key={page}
                      className="text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-full px-2 py-0.5"
                    >
                      Page {page}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {isAsking && (
          <div className="flex justify-start">
            <div className="bg-white text-gray-500 border border-indigo-100 rounded-2xl px-4 py-2 text-sm shadow-sm">
              Thinking...
            </div>
          </div>
        )}
      </div>

      {error && <p className="text-sm text-red-600 text-center">{error}</p>}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about the document..."
          disabled={isAsking}
          className="flex-1 rounded-lg border border-indigo-200 bg-white px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-50"
        />
        <button
          type="submit"
          disabled={isAsking || !question.trim()}
          className="rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:bg-gray-300 disabled:opacity-100 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </form>
    </div>
  );
}
