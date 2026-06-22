import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/executive", () => ({
  executiveService: { getCarbon: vi.fn() },
}));

import { executiveService } from "../../../api/executive";
import { CarbonReportCard } from "../CarbonReportCard";

describe("CarbonReportCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("happy path → total CO2 + Euro sınıf breakdown gösterilir", async () => {
    (executiveService.getCarbon as ReturnType<typeof vi.fn>).mockResolvedValue({
      period_start: "2026-04-27",
      period_end: "2026-05-27",
      total_co2_kg: 121_500,
      total_km: 180_000,
      co2_per_km: 0.675,
      benchmark_co2_per_km: 0.72,
      delta_pct: -6.2,
      by_euro_class: { VI: 80_000, V: 30_000, IV: 11_500 },
      top_emitters: [],
      vehicle_count: 25,
    });
    render(<CarbonReportCard />);
    await waitFor(() =>
      expect(screen.getByText("121.500")).toBeInTheDocument(),
    );
    expect(screen.getByText("0.68")).toBeInTheDocument();
    // Benchmark altı → success tonu
    expect(screen.getByText(/-6\.2%/)).toBeInTheDocument();
    // Euro sınıf badge'leri
    expect(screen.getByText(/Euro VI/)).toBeInTheDocument();
  });
});
