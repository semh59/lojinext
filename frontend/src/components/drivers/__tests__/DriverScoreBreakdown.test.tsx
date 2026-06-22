import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/drivers", () => ({
  driverService: {
    getScoreBreakdown: vi.fn(),
  },
}));

import { driverService } from "../../../api/drivers";
import { DriverScoreBreakdown } from "../DriverScoreBreakdown";

describe("DriverScoreBreakdown", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("formül kırılımını ve toplam skoru gösterir (yeterli sefer verisi varken)", async () => {
    (
      driverService.getScoreBreakdown as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      sofor_id: 7,
      ad_soyad: "Ali Veli",
      manual: 1.2,
      manual_weight: 0.4,
      auto: 1.08,
      auto_weight: 0.6,
      total: 1.13,
      trip_count: 12,
      avg_consumption: 27.8,
      target_reference: 30.0,
      has_trips: true,
    });

    render(<DriverScoreBreakdown driverId={7} />);

    await waitFor(() =>
      expect(screen.getByText("Toplam Hibrit Skor")).toBeInTheDocument(),
    );
    expect(screen.getByText("Manuel Puan")).toBeInTheDocument();
    expect(screen.getByText("Otomatik Puan")).toBeInTheDocument();
    expect(screen.getByText("1.13")).toBeInTheDocument();
    // ortalama tüketim metni
    expect(
      screen.getByText(/12 sefer · ort\. 27\.8 L\/100km/),
    ).toBeInTheDocument();
  });

  it("sefer verisi olmadığında uyarı + manuel puana eşitlenme mesajı", async () => {
    (
      driverService.getScoreBreakdown as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      sofor_id: 9,
      ad_soyad: "Yeni Sürücü",
      manual: 1.0,
      manual_weight: 0.4,
      auto: 1.0,
      auto_weight: 0.6,
      total: 1.0,
      trip_count: 0,
      avg_consumption: 0,
      target_reference: 30.0,
      has_trips: false,
    });

    render(<DriverScoreBreakdown driverId={9} />);

    await waitFor(() =>
      expect(
        screen.getByText(/henüz yeterli sefer verisi yok/),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByText(/Yeterli geçmiş sefer biriktiğinde/),
    ).toBeInTheDocument();
  });

  it("istek başarısız olursa hata mesajı", async () => {
    (
      driverService.getScoreBreakdown as ReturnType<typeof vi.fn>
    ).mockRejectedValue(new Error("boom"));
    render(<DriverScoreBreakdown driverId={1} />);
    await waitFor(() =>
      expect(screen.getByText("Skor kırılımı alınamadı")).toBeInTheDocument(),
    );
  });
});
