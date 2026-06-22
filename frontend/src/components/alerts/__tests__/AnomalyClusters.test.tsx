import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "../../../test/test-utils";

vi.mock("../../../api/anomalies", () => ({
  anomalyService: {
    getClusters: vi.fn().mockResolvedValue({
      period_days: 30,
      clusters: [
        {
          cluster_id: 0,
          size: 3,
          dominant_tip: "tuketim",
          dominant_kaynak_tip: "arac",
          severity_dagilim: { high: 3 },
          member_ids: [1, 2, 3],
          label: "3 adet high tuketim anomalisi (arac kaynaklı)",
          insight: null,
        },
      ],
    }),
  },
}));

describe("AnomalyClusters", () => {
  it("renders cluster labels", async () => {
    const { AnomalyClusters } = await import("../AnomalyClusters");
    render(<AnomalyClusters />);
    expect(await screen.findByText(/3 adet high tuketim/)).toBeInTheDocument();
  });
});
