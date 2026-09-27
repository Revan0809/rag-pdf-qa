"use client";

import { ChevronLeft, ChevronRight, FileWarning } from "lucide-react";
import { useEffect, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";

import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// Served as a plain static file from public/ (copied there by
// scripts/copy-pdf-worker.mjs on install) rather than bundled through
// webpack: the worker's top-level `import.meta` breaks Next's production
// minifier when it's pulled in via `new URL(..., import.meta.url)`. This
// also avoids depending on an external CDN for the worker.
pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

interface PdfViewerProps {
  file: File | null;
  docName: string | null;
  targetPage: number | null;
  citationSnippet: string | null;
}

export default function PdfViewer({ file, docName, targetPage, citationSnippet }: PdfViewerProps) {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState(1);

  useEffect(() => {
    setPageNumber(1);
    setNumPages(null);
  }, [file]);

  useEffect(() => {
    if (targetPage) setPageNumber(targetPage);
  }, [targetPage]);

  if (!docName) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-text-muted">
        Select a document from the library to preview it here.
      </div>
    );
  }

  if (!file) {
    // The backend is stateless and never stores the original PDF bytes
    // (only extracted text goes into Pinecone), so a preview only exists
    // for documents uploaded in this browser session/tab.
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center text-sm text-text-muted">
        <FileWarning size={20} aria-hidden="true" />
        <p>
          <span className="font-medium text-text">{docName}</span>
          <br />
          The original PDF isn&apos;t available to preview in this session. Chat still
          works normally — only the visual preview is affected.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-3 py-2 text-sm">
        <span className="truncate font-medium text-text">{docName}</span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setPageNumber((p) => Math.max(1, p - 1))}
            disabled={pageNumber <= 1}
            aria-label="Previous page"
            className="rounded p-1 text-text-muted hover:text-text disabled:opacity-30"
          >
            <ChevronLeft size={16} />
          </button>
          <span className="text-xs tabular-nums text-text-muted">
            {pageNumber}
            {numPages ? ` / ${numPages}` : ""}
          </span>
          <button
            type="button"
            onClick={() => setPageNumber((p) => (numPages ? Math.min(numPages, p + 1) : p + 1))}
            disabled={!!numPages && pageNumber >= numPages}
            aria-label="Next page"
            className="rounded p-1 text-text-muted hover:text-text disabled:opacity-30"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      <div className="quorum-scroll flex-1 overflow-auto bg-bg p-3">
        <Document
          file={file}
          onLoadSuccess={({ numPages: total }) => setNumPages(total)}
          loading={<p className="text-sm text-text-muted">Loading PDF…</p>}
          error={<p className="text-sm text-danger">Couldn&apos;t render this PDF.</p>}
          className="flex justify-center"
        >
          <Page pageNumber={pageNumber} renderAnnotationLayer renderTextLayer width={480} />
        </Document>
      </div>

      {citationSnippet && (
        <div className="border-t border-border bg-accent-from/5 px-3 py-2 text-xs text-text-muted">
          <span className="font-medium text-text">Cited passage: </span>
          {citationSnippet}
        </div>
      )}
    </div>
  );
}
