"use client";

import { Sparkles } from "lucide-react";

interface SuggestedQuestionsProps {
  questions: string[];
  onSelect: (question: string) => void;
}

export default function SuggestedQuestions({ questions, onSelect }: SuggestedQuestionsProps) {
  if (questions.length === 0) return null;

  return (
    <div className="flex flex-wrap justify-center gap-2">
      {questions.map((question) => (
        <button
          key={question}
          type="button"
          onClick={() => onSelect(question)}
          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1.5 text-sm text-text transition-colors hover:border-accent-from/50 hover:bg-accent-from/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-from"
        >
          <Sparkles size={13} className="text-accent-from" aria-hidden="true" />
          {question}
        </button>
      ))}
    </div>
  );
}
