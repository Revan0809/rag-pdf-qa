import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "PDF Q&A",
  description: "Ask questions about a PDF using RAG",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-white text-gray-900 min-h-screen">{children}</body>
    </html>
  );
}
