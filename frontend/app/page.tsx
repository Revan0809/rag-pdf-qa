"use client";

import { useState } from "react";

import ChatPanel from "@/components/ChatPanel";
import PdfUploader from "@/components/PdfUploader";
import type { UploadResponse } from "@/types";

export default function HomePage() {
  const [uploadedDoc, setUploadedDoc] = useState<UploadResponse | null>(null);

  return (
    <main className="flex flex-col items-center gap-8 px-4 py-16">
      <div className="text-center">
        <h1 className="bg-gradient-to-r from-indigo-600 via-purple-600 to-sky-600 bg-clip-text text-4xl font-bold text-transparent">
          PDF Q&A
        </h1>
        <p className="text-gray-500 mt-2">Upload a PDF, then ask questions about it.</p>
      </div>

      <div className="w-full max-w-2xl rounded-3xl border border-white/60 bg-white/70 p-6 sm:p-8 shadow-xl shadow-indigo-100 backdrop-blur-md">
        <PdfUploader onUploaded={setUploadedDoc} />

        {uploadedDoc && (
          <div className="w-full flex flex-col items-center gap-3 mt-8">
            <p className="text-xs font-medium text-indigo-500 bg-indigo-50 rounded-full px-3 py-1">
              {uploadedDoc.num_pages} page(s) · {uploadedDoc.num_chunks} chunk(s) indexed
            </p>
            <ChatPanel documentId={uploadedDoc.document_id} />
          </div>
        )}
      </div>
    </main>
  );
}
