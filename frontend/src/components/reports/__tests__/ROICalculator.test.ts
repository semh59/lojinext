import fs from "node:fs";
import path from "node:path";

describe("ROICalculator source guards", () => {
  it("reads user-facing copy from the reports resource catalog", () => {
    const source = fs.readFileSync(
      path.resolve(__dirname, "../ROICalculator.tsx"),
      "utf-8",
    );

    expect(source).toContain("useReportsResources");
    expect(source).not.toContain("Yatırım Simülasyonu");
  });
});
