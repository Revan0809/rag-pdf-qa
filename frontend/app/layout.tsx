import type { Metadata } from "next";

import { ToastProvider } from "@/components/Toast";

import "./globals.css";

export const metadata: Metadata = {
  title: "Quorum",
  description: "A team of AI agents that read, cross-check, and answer from your PDFs.",
};

// Sets data-theme before first paint so there's no flash of the wrong
// theme; reads the same key ThemeToggle/lib/storage.ts write to.
const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem("quorum:theme");
    var theme = stored === "light" || stored === "dark"
      ? stored
      : (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", theme);
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="relative min-h-screen overflow-x-hidden bg-bg text-text">
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
