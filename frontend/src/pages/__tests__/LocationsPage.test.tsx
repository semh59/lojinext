/**
 * 0-mock epiği Faz 2: bu sayfa testi statik operasyonel metni doğruluyor
 * (hiçbir assertion gerçek veri içeriğine bağlı değil) — bu yüzden
 * `useLocations`/`locationService` mock'ları KALDIRILDI, sayfa gerçek
 * backend'e karşı (bkz test/real-backend.ts) gerçekten monte edilip veri
 * çekiyor; sayfanın gerçek altyapıyla çökmeden render olduğunu da kanıtlar.
 * Kardeş bileşenler (LocationList/LocationFormModal/AnalysisModal/
 * DataExportImport) kendi ayrı test dosyalarında kapsanıyor — burada
 * dokümante mock'lu kalıyor (bu sayfanın kompozisyon/statik-metin testi,
 * onların veri mantığı testi değil). `useUrlState` (iç state, dış sınır
 * değil) ve `sonner` (UI side-effect) de dokümante mock'lu kalıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import { render, screen } from "../../test/test-utils";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../test/real-backend";

vi.mock("../../hooks/use-url-state", () => ({
  useUrlState: () => [{ search: "", zorluk: "", page: 1 }, vi.fn()],
}));

vi.mock("../../components/locations/LocationList", () => ({
  LocationList: () => <div>Location list</div>,
}));

vi.mock("../../components/locations/LocationFormModal", () => ({
  LocationFormModal: () => null,
}));

vi.mock("../../components/locations/AnalysisModal", () => ({
  AnalysisModal: () => null,
}));

vi.mock("../../components/shared/DataExportImport", () => ({
  DataExportImport: () => <div>toolbar</div>,
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("LocationsPage (real backend)", () => {
  let LocationsPage: typeof import("../LocationsPage").default;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ default: LocationsPage } = await import("../LocationsPage"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  // NOT: test-utils.tsx'in sardığı AuthProvider, axios-instance.ts'i STATIK
  // import zincirinden (beforeAll'daki vi.stubEnv'DEN ÖNCE) yüklüyor, bu
  // yüzden /auth/me çağrısı gerçek backend'e değil eski varsayılan baseURL'e
  // gidip ağ hatası veriyor (stderr'de görülür) — zararsız, bu test auth
  // durumuna bağlı değil (statik metin assertion'ları). LocationsPage'in
  // kendisi DİNAMİK import edildiği için (beforeAll'da, stubEnv'den SONRA)
  // gerçek useLocations/locationService zinciri doğru backend'e gider.
  it("renders truthful operational copy against the real backend and removes simulated map language", async () => {
    render(<LocationsPage />);

    expect(
      await screen.findByText(/Operasyonel Görünürlük/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Canlı harita veya simüle telemetri kullanılmaz/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Map Simulation/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Canlı Şebeke Analizi/i)).not.toBeInTheDocument();
  });
});
