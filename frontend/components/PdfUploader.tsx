"use client";

import { useCallback, useRef, useState } from "react";

import { uploadPdf } from "@/lib/api";
import type { UploadResponse, UploadStatus } from "@/types";

interface PdfUploaderProps {
  onUploaded: (result: UploadResponse) => void;
}

export default function PdfUploader({ onUploaded }: PdfUploaderProps) {
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [progress, setProgress] = useState(0);
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    async (file: File) => {
      if (file.type !== "application/pdf") {
        setStatus("error");
        setError("Please upload a PDF file.");
        return;
      }

      setFileName(file.name);
      setError(null);
      setStatus("uploading");
      setProgress(0);

      try {
        const result = await uploadPdf(file, (percent) => {
          setProgress(percent);
          if (percent === 100) setStatus("processing");
        });
        setStatus("success");
        onUploaded(result);
      } catch (err) {
        setStatus("error");
        setError(err instanceof Error ? err.message : "Upload failed.");
      }
    },
    [onUploaded]
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
  };

  const isBusy = status === "uploading" || status === "processing";

  return (
    <div className="w-full max-w-xl mx-auto">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDraggingOver(true);
        }}
        onDragLeave={() => setIsDraggingOver(false)}
        onDrop={handleDrop}
        onClick={() => !isBusy && fileInputRef.current?.click()}
        className={`flex flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed p-10 text-center transition-colors cursor-pointer
          ${isDraggingOver ? "border-indigo-500 bg-indigo-50" : "border-indigo-200 bg-white/60"}
          ${isBusy ? "cursor-not-allowed opacity-70" : "hover:border-indigo-400 hover:bg-indigo-50"}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={handleFileInputChange}
          disabled={isBusy}
        />

        <p className="text-gray-700 font-medium">
          {fileName ?? "Drag and drop a PDF here, or click to browse"}
        </p>
        <p className="text-sm text-gray-500">PDF files only</p>

        {isBusy && (
          <div className="w-full mt-4">
            <div className="h-2 w-full rounded-full bg-indigo-100 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all"
                style={{ width: `${status === "processing" ? 100 : progress}%` }}
              />
            </div>
            <p className="text-sm text-gray-500 mt-2">
              {status === "uploading" ? `Uploading... ${progress}%` : "Processing document..."}
            </p>
          </div>
        )}

        {status === "success" && (
          <p className="text-sm text-green-600 font-medium mt-2">
            Document ready — ask a question below.
          </p>
        )}

        {status === "error" && error && (
          <p className="text-sm text-red-600 font-medium mt-2">{error}</p>
        )}
      </div>
    </div>
  );
}
