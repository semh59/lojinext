import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/reports", () => ({
  reportService: {
    getCostAnalysis: vi.fn(),
  },
}));

import { reportService } from "../../../api/reports";
import { CostTrendChart } from "../CostTrendChart";

describe("CostTrendChart", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("boş veri için bilgi mesajı gösterir", async () => {
    (
      reportService.getCostAnalysis as ReturnType<typeof vi.fn>
    ).mockResolvedValue([]);
    render(<CostTrendChart />);
    await waitFor(() =>
      expect(
        screen.getByText("Bu dönem için gösterilecek maliyet verisi yok"),
      ).toBeInTheDocument(),
    );
  });

  it("veri varken başlık ve açıklama gösterir, boş mesaj göstermez", async () => {
    (
      reportService.getCostAnalysis as ReturnType<typeof vi.fn>
    ).mockResolvedValue([
      {
        month: 4,
        year: 2026,
        label: "Nis 26",
        fuel_cost: 100000,
        fuel_liters: 2500,
        trip_count: 12,
        total_distance: 8000,
        cost_per_km: 12.5,
        fuel: 100000,
        maintenance: 0,
      },
      {
        month: 5,
        year: 2026,
        label: "May 26",
        fuel_cost: 110000,
        fuel_liters: 2600,
        trip_count: 13,
        total_distance: 8500,
        cost_per_km: 13,
        fuel: 110000,
        maintenance: 0,
      },
    ]);

    render(<CostTrendChart />);

    await waitFor(() =>
      expect(
        screen.queryByText("Bu dönem için gösterilecek maliyet verisi yok"),
      ).not.toBeInTheDocument(),
    );
    expect(screen.getByText("Maliyet Trendi")).toBeInTheDocument();
    expect(
      screen.getByText("Aylık toplam litre ve litre başına ortalama fiyat"),
    ).toBeInTheDocument();
  });
});
