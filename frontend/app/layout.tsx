import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "PDF Q&A",
  description: "Ask questions about a PDF using RAG",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="relative min-h-screen overflow-x-hidden bg-slate-50 text-gray-900">
        <div
          aria-hidden
          className="pointer-events-none fixed inset-0 -z-10 bg-gradient-to-br from-indigo-100 via-slate-50 to-purple-100"
        />
        <div
          aria-hidden
          className="pointer-events-none fixed -top-40 -left-40 -z-10 h-96 w-96 rounded-full bg-indigo-300/40 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none fixed top-1/3 -right-32 -z-10 h-96 w-96 rounded-full bg-purple-300/40 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none fixed bottom-0 left-1/4 -z-10 h-96 w-96 rounded-full bg-sky-200/40 blur-3xl"
        />
        {children}
      </body>
    </html>
  );
}
