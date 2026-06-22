import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/executive", () => ({
  executiveService: { getCompliance: vi.fn() },
}));

import { executiveService } from "../../../api/executive";
import { ComplianceHeatmap } from "../ComplianceHeatmap";

describe("ComplianceHeatmap", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('empty → "yok" mesajı', async () => {
    (
      executiveService.getCompliance as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      days_horizon: 90,
      total_items: 0,
      overdue_count: 0,
      soon_count: 0,
      items: [],
    });
    render(<ComplianceHeatmap />);
    await waitFor(() =>
      expect(screen.getByText(/muayene yok/i)).toBeInTheDocument(),
    );
  });

  it("overdue + soon counts gösterilir", async () => {
    (
      executiveService.getCompliance as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      days_horizon: 90,
      total_items: 5,
      overdue_count: 2,
      soon_count: 3,
      items: [
        {
          entity_type: "arac",
          entity_id: 1,
          plaka: "34 ABC 111",
          field: "muayene",
          expiry_date: "2026-04-15",
          days_until: -42,
          risk_level: "overdue",
        },
        {
          entity_type: "dorse",
          entity_id: 99,
          plaka: "TRL 999",
          field: "muayene",
          expiry_date: "2026-06-05",
          days_until: 9,
          risk_level: "soon",
        },
      ],
    });
    render(<ComplianceHeatmap />);
    await waitFor(() => screen.getByText("34 ABC 111"));
    expect(screen.getByText(/2 Gecikmiş/)).toBeInTheDocument();
    expect(screen.getByText(/3 Yakında/)).toBeInTheDocument();
    expect(screen.getByText("TRL 999")).toBeInTheDocument();
    // v2 notu görünür
    expect(screen.getByText(/Tachograph AETR/)).toBeInTheDocument();
  });
});
