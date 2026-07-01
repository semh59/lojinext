import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/trips", () => ({
  tripService: {
    getTodayTrips: vi.fn(),
  },
}));

import { tripService } from "../../../api/trips";
import { TodaysActiveTrips } from "../TodaysActiveTrips";

function baseTrip(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: 1,
    arac_id: 1,
    sofor_id: 1,
    guzergah_id: 1,
    cikis_yeri: "Istanbul",
    varis_yeri: "Ankara",
    mesafe_km: 450,
    bos_agirlik_kg: 8000,
    dolu_agirlik_kg: 18000,
    net_kg: 10000,
    ton: 10,
    tarih: "2026-07-01",
    saat: "08:00",
    durum: "Planned",
    ...overrides,
  };
}

describe("TodaysActiveTrips", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("2026-07-01 fix: backend kanonik İngilizce durum değerlerini doğru Türkçe etikete çevirir (önceki Türkçe-anahtarlı sözlük her zaman miss ediyordu)", async () => {
    (tripService.getTodayTrips as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [
        baseTrip({ id: 1, durum: "Planned", sefer_no: "SEF-1" }),
        baseTrip({ id: 2, durum: "Completed", sefer_no: "SEF-2" }),
        baseTrip({ id: 3, durum: "Cancelled", sefer_no: "SEF-3" }),
      ],
      total: 3,
    });

    render(<TodaysActiveTrips />);

    await waitFor(() => expect(screen.getByText(/SEF-1/)).toBeInTheDocument());

    // Her üç durum da eski Türkçe-anahtarlı sözlükte hiç eşleşmiyordu — bu
    // yüzden ham backend string'i ("Planned"/"Completed"/"Cancelled") ekranda
    // hiç çevrilmeden görünüyordu. Fix sonrası doğru Türkçe etiketler basılır.
    expect(screen.getByText("Planlandı")).toBeInTheDocument();
    expect(screen.getByText("Tamamlandı")).toBeInTheDocument();
    expect(screen.getByText("İptal")).toBeInTheDocument();

    // Ham backend string'lerinin ekranda kalmadığını da doğrula (regresyon
    // guard'ı — eski bug tam olarak buydu).
    expect(screen.queryByText("Planned")).not.toBeInTheDocument();
    expect(screen.queryByText("Completed")).not.toBeInTheDocument();
    expect(screen.queryByText("Cancelled")).not.toBeInTheDocument();
  });

  it("gerçekten bilinmeyen bir durum değeri için nötr fallback rozeti gösterir", async () => {
    (tripService.getTodayTrips as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [
        baseTrip({ id: 1, durum: "TotallyUnknownStatus", sefer_no: "SEF-9" }),
      ],
      total: 1,
    });

    render(<TodaysActiveTrips />);

    await waitFor(() => expect(screen.getByText(/SEF-9/)).toBeInTheDocument());
    expect(screen.getByText("TotallyUnknownStatus")).toBeInTheDocument();
  });
});
