import { describe, it, expect } from "vitest";

import { safeHref } from "../utils";

describe("safeHref", () => {
  it("allows http/https URLs", () => {
    expect(safeHref("http://example.com")).toBe("http://example.com");
    expect(safeHref("https://example.com/a?b=c")).toBe(
      "https://example.com/a?b=c",
    );
  });

  it("allows mailto and tel", () => {
    expect(safeHref("mailto:a@b.com")).toBe("mailto:a@b.com");
    expect(safeHref("tel:+905320000000")).toBe("tel:+905320000000");
  });

  it("allows scheme-less relative URLs", () => {
    expect(safeHref("/trips/1")).toBe("/trips/1");
    expect(safeHref("#section")).toBe("#section");
  });

  it("blocks javascript: scheme (the XSS vector)", () => {
    expect(safeHref("javascript:alert(document.cookie)")).toBeUndefined();
    expect(safeHref("  JavaScript:alert(1)")).toBeUndefined();
  });

  it("blocks javascript: obfuscated with control/whitespace chars", () => {
    expect(safeHref("java\tscript:alert(1)")).toBeUndefined();
    expect(safeHref("java\nscript:alert(1)")).toBeUndefined();
    expect(safeHref("\x01javascript:alert(1)")).toBeUndefined();
  });

  it("blocks data: and vbscript: schemes", () => {
    expect(
      safeHref("data:text/html,<script>alert(1)</script>"),
    ).toBeUndefined();
    expect(safeHref("vbscript:msgbox(1)")).toBeUndefined();
  });

  it("returns undefined for empty / nullish input", () => {
    expect(safeHref("")).toBeUndefined();
    expect(safeHref(null)).toBeUndefined();
    expect(safeHref(undefined)).toBeUndefined();
  });
});
