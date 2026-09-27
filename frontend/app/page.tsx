"use client";

import { FileText, Library, MessageSquare } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import ChatPanel from "@/components/chat/ChatPanel";
import ColdStartBanner from "@/components/ColdStartBanner";
import QuorumLogo from "@/components/icons/QuorumLogo";
import DocumentList from "@/components/library/DocumentList";
import UploadDropzone from "@/components/library/UploadDropzone";
import ThemeToggle from "@/components/ThemeToggle";
import { useToast } from "@/components/Toast";
import { deleteDocument, getDocumentSummary } from "@/lib/api";
import { addToLibrary, loadLibrary, removeFromLibrary } from "@/lib/storage";
import type { Citation, DocumentSummary, LibraryDocument } from "@/types";

// pdf.js touches browser-only globals (DOMMatrix, Worker, ...) at import
// time, which crashes Next's server-side prerendering; load it client-only.
const PdfViewer = dynamic(() => import("@/components/viewer/PdfViewer"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-sm text-text-muted">
      Loading viewer…
    </div>
  ),
});

type MobileTab = "library" | "chat" | "viewer";

export default function HomePage() {
  const [library, setLibrary] = useState<LibraryDocument[]>([]);
  const [fileBlobs, setFileBlobs] = useState<Record<string, File>>({});
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [viewerDocId, setViewerDocId] = useState<string | null>(null);
  const [viewerTargetPage, setViewerTargetPage] = useState<number | null>(null);
  const [viewerSnippet, setViewerSnippet] = useState<string | null>(null);
  const [summaries, setSummaries] = useState<Record<string, DocumentSummary>>({});
  const [mobileTab, setMobileTab] = useState<MobileTab>("library");
  const { showToast } = useToast();

  useEffect(() => {
    setLibrary(loadLibrary());
  }, []);

  const handleUploaded = (doc: LibraryDocument, file: File) => {
    setLibrary(addToLibrary(doc));
    setFileBlobs((prev) => ({ ...prev, [doc.id]: file }));
    setSelectedIds((prev) => (prev.includes(doc.id) ? prev : [...prev, doc.id]));
    setViewerDocId(doc.id);
    setViewerTargetPage(null);
    setViewerSnippet(null);
    setMobileTab("chat");

    getDocumentSummary(doc.id)
      .then((summary) => setSummaries((prev) => ({ ...prev, [doc.id]: summary })))
      .catch(() => {
        // Suggested questions are a nice-to-have for the empty state; a
        // failure here shouldn't interrupt the upload flow with a toast.
      });
  };

  const handleToggleSelect = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const handleView = (id: string) => {
    setViewerDocId(id);
    setViewerTargetPage(null);
    setViewerSnippet(null);
    setMobileTab("viewer");
  };

  const handleDelete = async (id: string) => {
    const doc = library.find((d) => d.id === id);
    try {
      await deleteDocument(id);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to delete document.");
      return;
    }

    setLibrary(removeFromLibrary(id));
    setSelectedIds((prev) => prev.filter((x) => x !== id));
    setFileBlobs((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    if (viewerDocId === id) {
      setViewerDocId(null);
      setViewerTargetPage(null);
      setViewerSnippet(null);
    }
    showToast(`Deleted ${doc?.name ?? "document"}.`, "success");
  };

  const handleCitationClick = (citation: Citation) => {
    setViewerDocId(citation.doc_id);
    setViewerTargetPage(citation.page);
    setViewerSnippet(citation.snippet);
    setMobileTab("viewer");
  };

  const viewerDoc = library.find((d) => d.id === viewerDocId) ?? null;
  const suggestedQuestions = viewerDocId ? (summaries[viewerDocId]?.suggested_questions ?? []) : [];

  return (
    <div className="flex h-screen flex-col">
      <ColdStartBanner />

      <header className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <QuorumLogo className="h-7 w-7" />
          <div>
            <h1 className="text-lg font-semibold leading-none text-text">Quorum</h1>
            <p className="text-xs text-text-muted">A team of agents that read your PDFs</p>
          </div>
        </div>
        <ThemeToggle />
      </header>

      {library.length === 0 ? (
        <main className="flex flex-1 flex-col items-center justify-center gap-6 px-4 py-16">
          <QuorumLogo className="h-16 w-16" />
          <div className="text-center">
            <h2 className="bg-gradient-to-r from-accent-from via-accent-via to-accent-to bg-clip-text text-3xl font-bold text-transparent">
              Quorum
            </h2>
            <p className="mt-2 max-w-sm text-text-muted">
              Upload a PDF and a team of agents — a planner, retriever, analyst, and
              verifier — will read, cross-check, and answer questions from it.
            </p>
          </div>
          <div className="w-full max-w-md">
            <UploadDropzone onUploaded={handleUploaded} />
          </div>
        </main>
      ) : (
        <>
          <main className="grid flex-1 grid-cols-1 overflow-hidden md:grid-cols-[260px_1fr_360px]">
            <aside
              className={`quorum-scroll min-h-0 flex-col gap-3 overflow-y-auto border-r border-border p-3 md:flex ${
                mobileTab === "library" ? "flex" : "hidden"
              }`}
            >
              <UploadDropzone onUploaded={handleUploaded} />
              <DocumentList
                documents={library}
                selectedIds={selectedIds}
                activeViewerId={viewerDocId}
                onToggleSelect={handleToggleSelect}
                onView={handleView}
                onDelete={handleDelete}
              />
            </aside>

            <section
              className={`min-h-0 flex-col md:flex ${mobileTab === "chat" ? "flex" : "hidden"}`}
            >
              <ChatPanel
                selectedDocumentIds={selectedIds}
                suggestedQuestions={suggestedQuestions}
                onCitationClick={handleCitationClick}
              />
            </section>

            <aside
              className={`min-h-0 flex-col border-l border-border md:flex ${
                mobileTab === "viewer" ? "flex" : "hidden"
              }`}
            >
              <PdfViewer
                file={viewerDoc ? (fileBlobs[viewerDoc.id] ?? null) : null}
                docName={viewerDoc?.name ?? null}
                targetPage={viewerTargetPage}
                citationSnippet={viewerSnippet}
              />
            </aside>
          </main>

          <nav
            aria-label="Panels"
            className="grid grid-cols-3 border-t border-border md:hidden"
          >
            {(
              [
                { tab: "library", label: "Library", Icon: Library },
                { tab: "chat", label: "Chat", Icon: MessageSquare },
                { tab: "viewer", label: "Viewer", Icon: FileText },
              ] as const
            ).map(({ tab, label, Icon }) => (
              <button
                key={tab}
                type="button"
                onClick={() => setMobileTab(tab)}
                aria-current={mobileTab === tab}
                className={`flex flex-col items-center gap-0.5 py-2 text-xs ${
                  mobileTab === tab ? "text-accent-from" : "text-text-muted"
                }`}
              >
                <Icon size={18} />
                {label}
              </button>
            ))}
          </nav>
        </>
      )}
    </div>
  );
}
