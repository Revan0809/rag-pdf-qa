import type { LibraryDocument } from "@/types";

const LIBRARY_KEY = "quorum:library";
const THEME_KEY = "quorum:theme";

/**
 * The backend is stateless across requests (Render free tier has no disk),
 * so the list of "documents you've uploaded" lives here, in the browser,
 * keyed by the document_id Pinecone namespace. Losing this list doesn't
 * lose the vectors, just the friendly name/date shown for them.
 */
export function loadLibrary(): LibraryDocument[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(LIBRARY_KEY);
    return raw ? (JSON.parse(raw) as LibraryDocument[]) : [];
  } catch {
    return [];
  }
}

export function saveLibrary(documents: LibraryDocument[]): void {
  try {
    window.localStorage.setItem(LIBRARY_KEY, JSON.stringify(documents));
  } catch {
    // Storage full or unavailable (private browsing); the session still
    // works, it just won't remember documents on reload.
  }
}

export function addToLibrary(document: LibraryDocument): LibraryDocument[] {
  const next = [document, ...loadLibrary()];
  saveLibrary(next);
  return next;
}

export function removeFromLibrary(documentId: string): LibraryDocument[] {
  const next = loadLibrary().filter((doc) => doc.id !== documentId);
  saveLibrary(next);
  return next;
}

export type ThemePreference = "light" | "dark";

export function loadThemePreference(): ThemePreference | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(THEME_KEY);
    return raw === "light" || raw === "dark" ? raw : null;
  } catch {
    return null;
  }
}

export function saveThemePreference(theme: ThemePreference): void {
  try {
    window.localStorage.setItem(THEME_KEY, theme);
  } catch {
    // Ignore; theme just won't persist across visits.
  }
}
