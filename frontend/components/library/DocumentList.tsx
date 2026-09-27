"use client";

import { FileText, Trash2 } from "lucide-react";

import type { LibraryDocument } from "@/types";

interface DocumentListProps {
  documents: LibraryDocument[];
  selectedIds: string[];
  activeViewerId: string | null;
  onToggleSelect: (id: string) => void;
  onView: (id: string) => void;
  onDelete: (id: string) => void;
}

export default function DocumentList({
  documents,
  selectedIds,
  activeViewerId,
  onToggleSelect,
  onView,
  onDelete,
}: DocumentListProps) {
  if (documents.length === 0) {
    return (
      <p className="px-1 py-4 text-sm text-text-muted">
        No documents yet. Upload a PDF to get started.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-1">
      {documents.map((doc) => {
        const isSelected = selectedIds.includes(doc.id);
        const isActive = activeViewerId === doc.id;
        return (
          <li
            key={doc.id}
            className={`group flex items-center gap-2 rounded-lg px-2 py-2 text-sm transition-colors ${
              isActive ? "bg-accent-from/10" : "hover:bg-surface-hover"
            }`}
          >
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => onToggleSelect(doc.id)}
              aria-label={`Include ${doc.name} in the question`}
              className="h-4 w-4 shrink-0 rounded border-border text-accent-from focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-from"
            />

            <button
              type="button"
              onClick={() => onView(doc.id)}
              className="flex min-w-0 flex-1 items-center gap-2 text-left focus-visible:outline-none"
            >
              <FileText size={15} className="shrink-0 text-text-muted" />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium text-text">{doc.name}</span>
                <span className="block text-xs text-text-muted">{doc.pages} page(s)</span>
              </span>
            </button>

            <button
              type="button"
              onClick={() => onDelete(doc.id)}
              aria-label={`Delete ${doc.name}`}
              className="shrink-0 rounded p-1 text-text-muted opacity-0 transition-opacity hover:text-danger focus-visible:opacity-100 focus-visible:outline-none group-hover:opacity-100"
            >
              <Trash2 size={14} />
            </button>
          </li>
        );
      })}
    </ul>
  );
}
