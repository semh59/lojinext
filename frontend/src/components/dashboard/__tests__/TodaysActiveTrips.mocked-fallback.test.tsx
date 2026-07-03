/**
 * 0-mock epiği Faz 2: bu dosya BİLEREK mock'lu kalıyor (sibling
 * `TodaysActiveTrips.test.tsx` gerçek backend'e çevrildi). İki senaryo,
 * gerçek backend'den yapısal olarak elde edilemediği için burada kalıyor:
 *
 *  1. "Cancelled" durumu — backend'in `SeferReadService.get_all_paged`
 *     metodu `aktif_only=True` varsayılanıyla çalışıyor; `/trips/bulk/cancel`
 *     bir seferi iptal ettiğinde aktif=false yapıyor, bu yüzden iptal
 *     edilmiş sefer `GET /trips/today`'in `items` dizisinde asla
 *     görünmüyor (canlı curl ile doğrulandı: bulk/cancel sonrası
 *     `items: []` ama `meta.total: 1` — backend'in kendi total/items
 *     tutarsızlığı, bu epiğin kapsamı dışı ayrı bir backend konusu).
 *  2. Gerçekten bilinmeyen bir durum değeri — `TripStatus` DB CHECK
 *     constraint + Pydantic enum'u yalnızca Planned/Completed/Cancelled
 *     kabul eder; gerçek backend hiçbir zaman "TotallyUnknownStatus" gibi
 *     bilinmeyen bir değer dönemez.
 *
 * Her ikisi de saf frontend fallback/çeviri mantığını (tripStatusMetaFor
 * in ../TodaysActiveTrips.tsx) test ediyor, backend entegrasyonunu değil —
 * bu yüzden mock'lu kalmaları bilgi kaybı değil.
 */
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

describe("TodaysActiveTrips (mock'lu fallback senaryoları)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("Cancelled durumunu doğru Türkçe etikete çevirir (backend /trips/today bunu asla döndürmediği için mock'lu)", async () => {
    (tripService.getTodayTrips as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [baseTrip({ id: 3, durum: "Cancelled", sefer_no: "SEF-3" })],
      total: 1,
    });

    render(<TodaysActiveTrips />);

    await waitFor(() => expect(screen.getByText(/SEF-3/)).toBeInTheDocument());
    expect(screen.getByText("İptal")).toBeInTheDocument();
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
