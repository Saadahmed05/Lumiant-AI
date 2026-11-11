"use client";

import { Moon, Sun } from "lucide-react";

import { IconButton } from "@/components/ui/button";

const KEY = "lumiant-theme";

/**
 * Flips the theme and remembers the choice. Until a choice is saved the OS setting decides: public/theme-init.js puts
 * [data-theme="light"] on <html> for a light OS and leaves it off for a dark one, so the attribute is always the
 * effective theme.
 */
export function toggleTheme() {
  const root = document.documentElement;
  const next = root.dataset.theme === "light" ? "dark" : "light";
  root.dataset.theme = next;
  try {
    localStorage.setItem(KEY, next);
  } catch {
    // storage unavailable (private mode) — theme still applies for this page
  }
}

/** Forgets the saved choice and follows the OS setting again. */
export function matchSystemTheme() {
  const root = document.documentElement;
  try {
    localStorage.removeItem(KEY);
  } catch {
    // storage unavailable — nothing was saved
  }
  if (window.matchMedia?.("(prefers-color-scheme: light)").matches) root.dataset.theme = "light";
  else delete root.dataset.theme;
}

export function ThemeToggle() {
  // The icon follows the theme through CSS (`light:`), so server and client markup are identical.
  return (
    <IconButton onClick={toggleTheme} aria-label="Toggle light or dark theme">
      <Sun size={16} aria-hidden className="light:hidden" />
      <Moon size={16} aria-hidden className="hidden light:block" />
    </IconButton>
  );
}
