import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/executive", () => ({
  executiveService: { getBusFactor: vi.fn() },
}));

import { executiveService } from "../../../api/executive";
import { BusFactorWidget } from "../BusFactorWidget";

describe("BusFactorWidget", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('high risk → "Yüksek Risk" rozeti', async () => {
    (
      executiveService.getBusFactor as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      n: 3,
      top_n_drivers_loss_tl: 500_000,
      top_n_drivers: [
        { score: 1.8, yearly_km: 200_000 },
        { score: 1.7, yearly_km: 180_000 },
        { score: 1.6, yearly_km: 170_000 },
      ],
      bottlenecked_routes: [],
      risk_level: "high",
    });
    render(<BusFactorWidget />);
    await waitFor(() =>
      expect(screen.getByText("Yüksek Risk")).toBeInTheDocument(),
    );
    expect(screen.getByText(/₺500/)).toBeInTheDocument();
  });

  it("top_n_drivers PII koruması — sadece score + km gösterilir", async () => {
    (
      executiveService.getBusFactor as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      n: 1,
      top_n_drivers_loss_tl: 10_000,
      top_n_drivers: [{ score: 1.5, yearly_km: 100_000 }],
      bottlenecked_routes: [],
      risk_level: "low",
    });
    render(<BusFactorWidget />);
    await waitFor(() =>
      expect(screen.getByText(/KVKK koruması/)).toBeInTheDocument(),
    );
    // Sadece skor + km görünür
    expect(screen.getByText("1.50")).toBeInTheDocument();
    // Ad/ID kelimesi text'te olmamalı
    const text = document.body.textContent || "";
    expect(text).not.toMatch(/ad_soyad/i);
    expect(text).not.toMatch(/sofor_id/i);
  });
});
