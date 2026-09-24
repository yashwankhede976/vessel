import { useCallback, useEffect, useState } from "react";

/**
 * Theme management. Themes are applied by setting `data-theme` on the document
 * root; the CSS in styles/theme.css remaps the design tokens per theme. The
 * choice is persisted in localStorage so it survives reloads.
 */
export type ThemeName = "light" | "dark" | "contrast";

export const THEMES: ThemeName[] = ["light", "dark", "contrast"];

export const THEME_META: Record<ThemeName, { label: string; glyph: string }> = {
  light: { label: "Light", glyph: "☀" },
  dark: { label: "Dark", glyph: "☾" },
  contrast: { label: "High contrast", glyph: "◑" },
};

const STORAGE_KEY = "vessel:theme";

function readStoredTheme(): ThemeName {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "contrast") {
      return stored;
    }
  } catch {
    /* ignore storage access errors (private mode, etc.) */
  }
  return "light";
}

function applyTheme(theme: ThemeName) {
  const root = document.documentElement;
  if (theme === "light") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", theme);
  }
}

/** Apply the persisted theme as early as possible (call once at startup). */
export function initTheme() {
  applyTheme(readStoredTheme());
}

/** React hook: current theme + setter that persists and applies the choice. */
export function useTheme(): [ThemeName, (t: ThemeName) => void] {
  const [theme, setThemeState] = useState<ThemeName>(readStoredTheme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const setTheme = useCallback((t: ThemeName) => {
    setThemeState(t);
    try {
      localStorage.setItem(STORAGE_KEY, t);
    } catch {
      /* ignore */
    }
  }, []);

  return [theme, setTheme];
}
