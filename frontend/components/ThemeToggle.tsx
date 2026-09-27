"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { saveThemePreference, type ThemePreference } from "@/lib/storage";

export default function ThemeToggle() {
  // The inline script in layout.tsx already set data-theme before paint;
  // read it back here so the icon matches on first client render.
  const [theme, setTheme] = useState<ThemePreference>("light");

  useEffect(() => {
    const current = document.documentElement.getAttribute("data-theme");
    setTheme(current === "dark" ? "dark" : "light");
  }, []);

  const toggle = () => {
    const next: ThemePreference = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    saveThemePreference(next);
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-border text-text-muted transition-colors hover:bg-surface-hover hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-from"
    >
      {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}
