"use client";

import { FileUp, Loader2 } from "lucide-react";
import { useCallback, useRef, useState } from "react";

import { uploadPdf } from "@/lib/api";
import { useToast } from "@/components/Toast";
import type { LibraryDocument, UploadStatus } from "@/types";

interface UploadDropzoneProps {
  onUploaded: (doc: LibraryDocument, file: File) => void;
}

export default function UploadDropzone({ onUploaded }: UploadDropzoneProps) {
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [progress, setProgress] = useState(0);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { showToast } = useToast();

  const handleFile = useCallback(
    async (file: File) => {
      if (file.type !== "application/pdf") {
        showToast("Please upload a PDF file.");
        return;
      }

      setStatus("uploading");
      setProgress(0);

      try {
        const result = await uploadPdf(file, (percent) => {
          setProgress(percent);
          if (percent === 100) setStatus("processing");
        });
        setStatus("success");
        onUploaded(
          {
            id: result.document_id,
            name: result.doc_name,
            pages: result.num_pages,
            uploadedAt: new Date().toISOString(),
          },
          file
        );
        window.setTimeout(() => setStatus("idle"), 1500);
      } catch (err) {
        setStatus("error");
        showToast(err instanceof Error ? err.message : "Upload failed.");
        window.setTimeout(() => setStatus("idle"), 1500);
      }
    },
    [onUploaded, showToast]
  );

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDraggingOver(false);
    const file = event.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  const handleFileInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) handleFile(file);
    event.target.value = "";
  };

  const isBusy = status === "uploading" || status === "processing";

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setIsDraggingOver(true);
      }}
      onDragLeave={() => setIsDraggingOver(false)}
      onDrop={handleDrop}
      onClick={() => !isBusy && fileInputRef.current?.click()}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && !isBusy) fileInputRef.current?.click();
      }}
      role="button"
      tabIndex={0}
      aria-label="Upload a PDF"
      className={`flex flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed p-6 text-center text-sm transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-from
        ${isDraggingOver ? "border-accent-from bg-accent-from/5" : "border-border bg-surface"}
        ${isBusy ? "cursor-not-allowed opacity-70" : "hover:border-accent-from/60 hover:bg-accent-from/5"}`}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={handleFileInputChange}
        disabled={isBusy}
      />

      {isBusy ? (
        <Loader2 size={20} className="animate-spin text-accent-from" />
      ) : (
        <FileUp size={20} className="text-text-muted" />
      )}

      <p className="text-text-muted">
        {status === "uploading"
          ? `Uploading… ${progress}%`
          : status === "processing"
            ? "Processing document…"
            : "Drop a PDF here, or click to browse"}
      </p>
    </div>
  );
}
