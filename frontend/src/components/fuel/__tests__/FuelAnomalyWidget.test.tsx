import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/anomalies", () => ({
  anomalyService: {
    getRecentAnomalies: vi.fn(),
  },
}));

import { anomalyService } from "../../../api/anomalies";
import { FuelAnomalyWidget } from "../FuelAnomalyWidget";

describe("FuelAnomalyWidget", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("anomali yokken pozitif mesaj gösterir", async () => {
    (
      anomalyService.getRecentAnomalies as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      anomalies: [],
      total: 0,
      filters: { days: 30, severity: null, tip: "tuketim" },
    });

    render(<FuelAnomalyWidget />);

    await waitFor(() =>
      expect(
        screen.getByText("Son 30 günde yakıt anomalisi tespit edilmedi"),
      ).toBeInTheDocument(),
    );
  });

  it("anomali listesi renderlanır ve severity rozeti gösterilir", async () => {
    (
      anomalyService.getRecentAnomalies as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      anomalies: [
        {
          id: 1,
          tarih: "2026-05-19T10:00:00",
          tip: "tuketim",
          kaynak_tip: "arac",
          kaynak_id: 7,
          deger: 42.1,
          beklenen_deger: 31.5,
          sapma_yuzde: 33.7,
          severity: "high",
          aciklama: "Aşırı tüketim",
          plaka: "34 ABC 123",
          sofor_adi: "Ali Veli",
        },
      ],
      total: 1,
      filters: { days: 30, severity: null, tip: "tuketim" },
    });

    render(<FuelAnomalyWidget />);

    await waitFor(() =>
      expect(screen.getByText("34 ABC 123")).toBeInTheDocument(),
    );
    expect(screen.getByText(/Ali Veli/)).toBeInTheDocument();
    expect(screen.getByText(/\+33\.7%/)).toBeInTheDocument();
    expect(screen.getByText("Yüksek")).toBeInTheDocument();
  });

  it('toplam > liste boyu olunca "Tüm Anomaliler" linki çıkar', async () => {
    (
      anomalyService.getRecentAnomalies as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      anomalies: [
        {
          id: 1,
          tarih: "2026-05-19",
          tip: "tuketim",
          kaynak_tip: "arac",
          kaynak_id: 7,
          deger: 42,
          beklenen_deger: 31,
          sapma_yuzde: 35,
          severity: "medium",
          aciklama: "",
          plaka: "34 X",
        },
      ],
      total: 12,
      filters: { days: 30, severity: null, tip: "tuketim" },
    });

    render(<FuelAnomalyWidget />);

    const link = await screen.findByRole("link", { name: /Tüm Anomaliler/ });
    expect(link).toHaveAttribute("href", "/alerts?days=30&tip=tuketim");
  });
});
