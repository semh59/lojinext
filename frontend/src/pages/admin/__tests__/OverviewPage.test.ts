import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("OverviewPage source guard", () => {
  it("uses resource-based Turkish copy and does not contain placeholder copy", () => {
    const filePath = resolve(process.cwd(), "src/pages/admin/OverviewPage.tsx");
    const source = readFileSync(filePath, "utf-8");

    expect(source).not.toMatch(/çok yakında/i);
    expect(source).toContain("resources/tr/admin");
    expect(source).not.toMatch(/Sistem Genel Bakış/i);
  });
});
