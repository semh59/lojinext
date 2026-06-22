import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/executive", () => ({
  executiveService: { runWhatIf: vi.fn() },
}));

import { executiveService } from "../../../api/executive";
import { WhatIfPanel } from "../WhatIfPanel";

describe("WhatIfPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("default scenario fleet_renewal — buton tıklanır + sonuç görünür", async () => {
    (executiveService.runWhatIf as ReturnType<typeof vi.fn>).mockResolvedValue({
      scenario_type: "fleet_renewal",
      inputs: {},
      yearly_savings_tl: 697_500,
      upfront_cost_tl: 6_000_000,
      payback_years: 8.6,
      five_year_roi_pct: -42.0,
      co2_reduction_kg: 12_000,
      confidence: 0.8,
      monte_carlo: null,
      reasons: ["3 araç 15+ yaş"],
    });
    render(<WhatIfPanel />);
    fireEvent.click(
      screen.getByRole("button", { name: /Senaryoyu Çalıştır/i }),
    );
    await waitFor(() =>
      expect(screen.getByText(/₺697\.500/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/8\.6 yıl/)).toBeInTheDocument();
    // CO2 azaltımı görünür
    expect(screen.getByText(/12\.000 kg/)).toBeInTheDocument();
  });

  it("Monte Carlo P10/P50/P90 bandı görünür (route_portfolio)", async () => {
    (executiveService.runWhatIf as ReturnType<typeof vi.fn>).mockResolvedValue({
      scenario_type: "route_portfolio",
      inputs: {},
      yearly_savings_tl: 150_000,
      upfront_cost_tl: 0,
      payback_years: 0,
      five_year_roi_pct: 0,
      co2_reduction_kg: 0,
      confidence: 0.65,
      monte_carlo: {
        p10: 80_000,
        p50: 150_000,
        p90: 220_000,
        iterations: 100,
      },
      reasons: ["3 güzergah elenecek"],
    });
    render(<WhatIfPanel />);
    // Senaryo değiştir
    fireEvent.click(
      screen.getByRole("button", {
        name: /Güzergah Portföy Optimizasyonu/i,
      }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: /Senaryoyu Çalıştır/i }),
    );
    await waitFor(() =>
      expect(screen.getByText(/₺220\.000/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/P10 \(kötümser\)/i)).toBeInTheDocument();
    expect(screen.getByText(/P90 \(iyimser\)/i)).toBeInTheDocument();
  });
});
