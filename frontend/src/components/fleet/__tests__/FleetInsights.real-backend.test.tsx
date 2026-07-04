/**
 * 0-mock epiği: FleetInsights.test.tsx'in mock'lu senaryolarına ek olarak,
 * gerçek backend'e karşı "vehicles" sekmesi senaryoları.
 *
 * "vehicles" sekmesinde bileşen SADECE orval-tabanlı client'lar kullanır:
 * vehicleService.getFleetStats → GET /api/v1/vehicles/fleet-stats
 * reportService.getDashboardStats → GET /api/v1/reports/dashboard
 * İkisi de generated/api/*.ts içinde tam "/api/v1/..." path'i axios url'e
 * gömülü halde kullanır (bkz src/api/vehicles.ts, src/api/reports.ts) — bu
 * yüzden VITE_API_URL = REAL_BACKEND_ORIGIN (sadece origin, /api/v1 EK
 * DEĞİL).
 *
 * "trailers" sekmesi DÖNÜŞTÜRÜLMEDİ (mock'lu dosyada kalıyor): o sekme
 * dorseService.getFleetStats kullanıyor
 * (src/services/dorseService.ts:26-31), bu servis axiosInstance'ı elle
 * ("/trailers/fleet-stats") ÇAĞRISIYLA, /api/v1 prefix'i URL'e GÖMMEDEN
 * çağırıyor — yani aynı axiosInstance'ın baseURL'inin literal "/api/v1"
 * OLMASINI bekliyor. Ama aynı render'da reportService (dashboard sorgusu,
 * useQuery'de `enabled` koşulu YOK — her sekmede her zaman ateşleniyor)
 * orval-tabanlı ve baseURL'in origin-only olmasını gerektiriyor. Aynı
 * axiosInstance örneği için tek bir baseURL seçilebildiğinden, bu iki
 * gereksinim ayrılamaz bir çakışma oluşturuyor (curl ile doğrulandı: origin
 * + "/api/v1" baseURL + orval'ın kendi "/api/v1/..." path'i →
 * "/api/v1/api/v1/..." → 404; origin-only baseURL + dorseService'in
 * relative "/trailers/fleet-stats" path'i → "/trailers/fleet-stats"
 * (prefix'siz) → 404). Bu, üç dosyalık bu görevin kapsamı dışında,
 * dorseService'in mimari tutarsızlığından kaynaklanan ayrı bir konu; "trailers"
 * sekmesi testi bu yüzden mock'lu dosyada bırakıldı.
 *
 * Yükleme-iskeleti senaryosu (never-resolving promise) gerçek ağ isteğiyle
 * deterministik tetiklenemediği için o da mock'lu dosyada kalıyor.
 *
 * Test DB'sinde birkaç kalıcı satır var (boş değil) VE bu 0-mock epiğinde
 * paralel çalışan diğer ajanlar aynı DB'yi eş-zamanlı mutasyona uğratabiliyor
 * — bu yüzden sayıları hardcode etmek yerine HER `it` içinde render'dan
 * hemen önce gerçek backend'den taze fetch ediyoruz (yarış penceresini
 * minimize eder) ve kart değerlerini etiket metnine göre SCOPE'layarak
 * okuyoruz (`getByText(label)` → aynı kartın value span'i) — aksi halde iki
 * farklı kartın değeri tesadüfen eşitse (örn. aktif=1 ve muayene toplamı=1)
 * `getByText(String(n))` "multiple elements" hatasıyla flaky patlıyor
 * (canlı testte tam olarak bu senaryo yakalandı).
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, className, ...rest }: any) => (
      <div className={className} {...rest}>
        {children}
      </div>
    ),
  },
}));

const backendUp = await isRealBackendReachable();

interface VehicleFleetStats {
  total: number;
  active: number;
  inspection_expiring: number;
  inspection_overdue: number;
}

describe.skipIf(!backendUp)(
  "FleetInsights — Araçlar Sekmesi (real backend)",
  () => {
    let render: typeof import("../../../test/test-utils").render;
    let screen: typeof import("../../../test/test-utils").screen;
    let waitFor: typeof import("../../../test/test-utils").waitFor;
    let FleetInsights: typeof import("../FleetInsights").FleetInsights;
    let authToken: string;

    beforeAll(async () => {
      vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
      authToken = await loginAsAdmin();
      sessionStorage.setItem("access_token", authToken);
      ({ render, screen, waitFor } = await import("../../../test/test-utils"));
      ({ FleetInsights } = await import("../FleetInsights"));
    });

    afterAll(() => {
      vi.unstubAllEnvs();
    });

    async function fetchRealFleetSnapshot(): Promise<{
      fleetStats: VehicleFleetStats;
      toplamSefer: number;
    }> {
      const authHeaders = { Authorization: `Bearer ${authToken}` };
      const [fleetResp, dashResp] = await Promise.all([
        fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/fleet-stats`, {
          headers: authHeaders,
        }),
        fetch(`${REAL_BACKEND_ORIGIN}/api/v1/reports/dashboard`, {
          headers: authHeaders,
        }),
      ]);
      const fleetStats = (await fleetResp.json()) as VehicleFleetStats;
      const dashboard = await dashResp.json();
      return { fleetStats, toplamSefer: dashboard.toplam_sefer };
    }

    /** Kart başlığına göre scope'lu value okuma — aynı sayı iki farklı
     * kartta tesadüfen tekrarlanırsa `getByText(String(n))`'in "multiple
     * elements" hatasıyla flaky patlamasını önler. */
    function getCardValue(labelText: string): string {
      const label = screen.getByText(labelText);
      const card = label.closest(
        "div.rounded-card, button.rounded-card",
      ) as HTMLElement;
      const valueSpan = card.querySelector("span.text-3xl");
      return valueSpan?.textContent ?? "";
    }

    it("gerçek backend'den toplam + aktif araç sayılarını gösterir", async () => {
      sessionStorage.setItem("access_token", authToken);
      const { fleetStats } = await fetchRealFleetSnapshot();
      render(<FleetInsights activeTab="vehicles" />);

      await waitFor(
        () => {
          expect(getCardValue("Toplam Araç")).toBe(String(fleetStats.total));
          expect(getCardValue("Aktif Araç")).toBe(String(fleetStats.active));
        },
        { timeout: 10000 },
      );
    }, 15000);

    it("muayene uyarı kartı: overdue + expiring toplamını ve sefer sayısını gösterir", async () => {
      sessionStorage.setItem("access_token", authToken);
      const { fleetStats, toplamSefer } = await fetchRealFleetSnapshot();
      render(<FleetInsights activeTab="vehicles" />);

      const expectedInspectionCount =
        fleetStats.inspection_overdue + fleetStats.inspection_expiring;

      await waitFor(
        () => {
          expect(getCardValue("Muayene Uyarısı")).toBe(
            String(expectedInspectionCount),
          );
          expect(getCardValue("Toplam Sefer")).toBe(String(toplamSefer));
        },
        { timeout: 10000 },
      );
    }, 15000);

    it("muayene durumuna göre doğru renk kenarlığı gösterir (backend gerçek verisine göre)", async () => {
      sessionStorage.setItem("access_token", authToken);
      const { fleetStats } = await fetchRealFleetSnapshot();
      render(<FleetInsights activeTab="vehicles" />);

      const hasInspectionIssue =
        fleetStats.inspection_overdue > 0 || fleetStats.inspection_expiring > 0;
      const expectedSelector = hasInspectionIssue
        ? ".border-l-warning\\/60"
        : ".border-l-success\\/60";

      await waitFor(
        () => {
          expect(document.querySelector(expectedSelector)).toBeInTheDocument();
        },
        { timeout: 10000 },
      );
    }, 15000);
  },
);
