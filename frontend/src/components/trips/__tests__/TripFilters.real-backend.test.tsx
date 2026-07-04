/**
 * 0-mock epiği: TripFilters.test.tsx'in mock'lu senaryolarına ek olarak,
 * gerçek backend'e karşı bir senaryo. `preferenceService.getPreferences`
 * mount'ta her zaman çağrılır (modul="seferler", ayar_tipi="filtre") —
 * burada bunu gerçek bir HTTP round-trip ile doğruluyoruz (boş liste döner,
 * "kayıtlı filtre" bölümü render edilmez, bileşen çökmez).
 *
 * `preferenceService.savePreference`/`deletePreference` senaryoları mock'lu
 * dosyada kalıyor — test ortamında yalnızca sistem (synthetic super admin,
 * id<=0) hesabı mevcut ve backend bu hesabın `POST /preferences` çağırmasını
 * kasıtlı olarak reddediyor (`HTTP_403 "Sistem kullanıcısı tercih
 * kaydedemez"` — curl ile doğrulandı, gerçek bir iş kuralı, bug değil; bkz
 * QuietHoursSettings.real-backend.test.tsx aynı kısıt için).
 *
 * `useTripStore` (yerel Zustand state) ve `DataExportImport` (ilgisiz alt
 * bileşen) burada da mock'lanıyor — bunlar backend çağrısı değil.
 */
import { beforeAll, afterAll, describe, expect, it, vi } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const mockSetFilters = vi.fn();
const mockResetFilters = vi.fn();

vi.mock("../../../stores/use-trip-store", () => ({
  useTripStore: () => ({
    filters: {
      durum: "",
      search: "",
      baslangic_tarih: "",
      bitis_tarih: "",
      onay_durumu: undefined,
      arac_id: undefined,
      sofor_id: undefined,
    },
    setFilters: mockSetFilters,
    resetFilters: mockResetFilters,
  }),
}));

vi.mock("../../../components/shared/DataExportImport", () => ({
  DataExportImport: () => <div data-testid="export-import" />,
}));

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("TripFilters (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let TripFilters: typeof import("../TripFilters").TripFilters;
  let authToken: string;

  const defaultProps = {
    onExport: vi.fn().mockResolvedValue(undefined),
    onImport: vi.fn().mockResolvedValue(undefined),
    onDownloadTemplate: vi.fn().mockResolvedValue(undefined),
  };

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, fireEvent, waitFor } = await import(
      "../../../test/test-utils"
    ));
    ({ TripFilters } = await import("../TripFilters"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("gerçek backend'den boş kayıtlı-filtre listesi döner, panel çökmeden açılır", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<TripFilters {...defaultProps} />);

    fireEvent.click(screen.getByRole("button", { name: /filtrele/i }));

    await waitFor(() => {
      expect(screen.getByText(/gelişmiş filtre/i)).toBeInTheDocument();
    });

    // Backend boş liste döndüğü için "kayıtlı filtreler" bölümü render edilmez.
    expect(screen.queryByText(/kayıtlı filtre/i)).not.toBeInTheDocument();
  });
});
