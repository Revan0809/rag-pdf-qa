"use client";

import { FileText } from "lucide-react";

import type { Citation } from "@/types";

interface CitationChipProps {
  citation: Citation;
  onClick: (citation: Citation) => void;
}

export default function CitationChip({ citation, onClick }: CitationChipProps) {
  return (
    <button
      type="button"
      onClick={() => onClick(citation)}
      title={citation.snippet}
      className="inline-flex items-center gap-1 rounded-full border border-accent-from/30 bg-accent-from/10 px-2 py-0.5 text-xs font-medium text-accent-from transition-colors hover:bg-accent-from/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-from"
    >
      <FileText size={11} aria-hidden="true" />
      {citation.doc_name}, p.{citation.page}
    </button>
  );
}
