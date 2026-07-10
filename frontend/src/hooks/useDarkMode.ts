import { useEffect, useState } from "react";

/**
 * Was previously defined only inside AppLayout.tsx — AdminLayout.tsx (which
 * wraps every /admin/* page) never called it, so the <html> "dark" class
 * was only ever applied when AppLayout itself mounted first. Landing
 * directly on an admin page (fresh tab, hard refresh, bookmark) skipped
 * that entirely: localStorage still said "dark", but the class was never
 * toggled on, so the whole admin panel silently rendered in light mode
 * regardless of the user's saved preference.
 */
export function useDarkMode() {
  const [isDark, setIsDark] = useState(() => {
    const stored = localStorage.getItem("theme");
    if (stored) return stored === "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
    localStorage.setItem("theme", isDark ? "dark" : "light");
  }, [isDark]);

  return { isDark, toggle: () => setIsDark((p) => !p) };
}
