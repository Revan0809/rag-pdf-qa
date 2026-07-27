"use client";

import { useState } from "react";

import ChatPanel from "@/components/ChatPanel";
import PdfUploader from "@/components/PdfUploader";
import type { UploadResponse } from "@/types";

export default function HomePage() {
  const [uploadedDoc, setUploadedDoc] = useState<UploadResponse | null>(null);

  return (
    <main className="flex flex-col items-center gap-10 px-4 py-16">
      <div className="text-center">
        <h1 className="text-3xl font-semibold">PDF Q&A</h1>
        <p className="text-gray-500 mt-1">Upload a PDF, then ask questions about it.</p>
      </div>

      <PdfUploader onUploaded={setUploadedDoc} />

      {uploadedDoc && (
        <div className="w-full flex flex-col items-center gap-2">
          <p className="text-xs text-gray-400">
            {uploadedDoc.num_pages} page(s) · {uploadedDoc.num_chunks} chunk(s) indexed
          </p>
          <ChatPanel documentId={uploadedDoc.document_id} />
        </div>
      )}
    </main>
  );
}
