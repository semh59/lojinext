import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Returns `url` only when it is safe to use as an `<a href>`, otherwise
 * `undefined` (an anchor without href is not navigable).
 *
 * React does NOT sanitize href schemes, so a user-supplied
 * `javascript:` / `data:` / `vbscript:` URL would execute script when clicked.
 * This allow-lists http/https/mailto/tel and same-origin relative URLs, and
 * strips control/whitespace chars first to defeat obfuscation like
 * `java\tscript:`.
 */
export function safeHref(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  const trimmed = url.trim();
  const collapsed = trimmed.replace(/[\x00-\x1f\x7f\s]/g, "").toLowerCase();
  const scheme = collapsed.match(/^([a-z][a-z0-9+.-]*):/);
  if (scheme && !["http", "https", "mailto", "tel"].includes(scheme[1])) {
    return undefined;
  }
  return trimmed;
}
