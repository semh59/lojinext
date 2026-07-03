/**
 * 0-mock epiği Faz 2: bu bileşen Driver/Sofor domain'inin bir XAI özelliği
 * (GET /drivers/{id}/route-profile) — Route/Location domain'i değil.
 * Buradaki 3 senaryo (best_route_type var/yok, hiç sefer yok) gerçek bir
 * Sofor + rota-tipi sınıflandırılmış Sefer geçmişi seed'i gerektirir — bu,
 * Driver/Sefer domain'inin kendi seed altyapısı, frontend'in kendi API
 * yüzeyinden erişilebilir değil ve bu epiğin Route/Location kapsamı
 * dışında. Dokümante mock'lu kalıyor. "İstek başarısız" senaryosu (var
 * olmayan sofor_id → gerçek 404, seed gerektirmez) gerçek backend'e
 * çevrilip ayrı bir dosyada (DriverRouteProfile.real-backend.test.tsx)
 * ele alındı — vi.mock tüm dosyayı etkilediği için aynı dosyada hem
 * mock'lu hem gerçek test tutmak modül-cache çakışmasına yol açıyordu.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/drivers", () => ({
  driverService: {
    getRouteProfile: vi.fn(),
  },
}));

import { driverService } from "../../../api/drivers";
import { DriverRouteProfile } from "../DriverRouteProfile";

const profileWithBest = {
  sofor_id: 7,
  ad_soyad: "Ali Veli",
  min_trips_for_best: 5,
  best_route_type: "highway_dominant" as const,
  profiles: [
    {
      route_type: "highway_dominant" as const,
      label: "Otoyol Ağırlıklı",
      trip_count: 12,
      avg_actual: 27.5,
      avg_predicted: 30.0,
      deviation_pct: -8.3,
    },
    {
      route_type: "mountain" as const,
      label: "Dağlık",
      trip_count: 6,
      avg_actual: 33.0,
      avg_predicted: 31.0,
      deviation_pct: 6.5,
    },
    {
      route_type: "urban" as const,
      label: "Şehir İçi",
      trip_count: 0,
      avg_actual: 0,
      avg_predicted: 0,
      deviation_pct: 0,
    },
    {
      route_type: "mixed" as const,
      label: "Karışık",
      trip_count: 3,
      avg_actual: 30.0,
      avg_predicted: 30.5,
      deviation_pct: -1.6,
    },
  ],
};

describe("DriverRouteProfile", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("best_route_type olduğunda Trophy + label gösterir", async () => {
    (
      driverService.getRouteProfile as ReturnType<typeof vi.fn>
    ).mockResolvedValue(profileWithBest);
    render(<DriverRouteProfile driverId={7} />);
    await waitFor(() =>
      expect(screen.getByText("En Güçlü Güzergah Tipi")).toBeInTheDocument(),
    );
    expect(
      screen.getAllByText("Otoyol Ağırlıklı").length,
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/-8\.3%/)).toBeInTheDocument();
  });

  it("best_route_type yoksa uyarı banner gösterir", async () => {
    (
      driverService.getRouteProfile as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      ...profileWithBest,
      best_route_type: null,
    });
    render(<DriverRouteProfile driverId={7} />);
    await waitFor(() =>
      expect(
        screen.getByText(
          /Henüz en güçlü güzergah tipini belirlemek için yeterli veri yok/,
        ),
      ).toBeInTheDocument(),
    );
  });

  it("hiç sefer yoksa boş-state mesajı", async () => {
    (
      driverService.getRouteProfile as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      ...profileWithBest,
      best_route_type: null,
      profiles: profileWithBest.profiles.map((p) => ({
        ...p,
        trip_count: 0,
        avg_actual: 0,
        avg_predicted: 0,
        deviation_pct: 0,
      })),
    });
    render(<DriverRouteProfile driverId={7} />);
    await waitFor(() =>
      expect(
        screen.getByText("Bu şoför için henüz rota analizli sefer bulunmuyor."),
      ).toBeInTheDocument(),
    );
  });
});
