/**
 * 0-mock epiği: DownloadPdfButton.test.tsx'in mock'lu "happy path"
 * senaryosunun gerçek karşılığı — `GET /reports/executive/pdf` backend'de
 * asla 404 döndürmez (tüm alt-motorlar hata verse de graceful degrade edip
 * 200 + PDF bytes döner, bkz app/api/v1/endpoints/executive.py:684). Bu
 * yüzden mock'lu dosyadaki "404 → henüz hazır değil" senaryosu gerçek
 * backend'e çevrilemiyor (üretilemeyen bir durum) — mock'lu dosyada kalıyor.
 *
 * jsdom `URL.createObjectURL` desteklemediği için (bileşenin blob→link
 * indirme akışının bir parçası, test edilen asıl davranış değil) burada
 * stub'lanıyor.
 *
 * BaseURL gotcha: `executiveService.downloadPdf` orval-üretilmiş bir client
 * DEĞİL — doğrudan `axiosInstance.get("/reports/executive/pdf")` çağırıyor
 * (path "/api/v1" önekini İÇERMİYOR, orval client'ların aksine). Bu yüzden
 * burada `VITE_API_URL` diğer real-backend dosyalarındaki gibi
 * REAL_BACKEND_ORIGIN değil, REAL_BACKEND_URL (origin+"/api/v1") olarak
 * stub'lanıyor — aksi halde istek "/reports/executive/pdf" (öneksiz) gerçek
 * 404'e düşer.
 *
 * NotificationContext hâlâ mock'lu: test-utils.tsx'teki AllTheProviders
 * NotificationProvider içermiyor (useNotify Provider dışında çağrılırsa
 * throw eder) — bu backend'den bağımsız, saf bir test-altyapısı gereği,
 * "harmless UI-lib mock" kategorisinde (bkz SendCoachingDialog.real-backend
 * .test.tsx emsali).
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";

vi.mock("../../../context/NotificationContext", async () => {
  const actual = await vi.importActual<any>(
    "../../../context/NotificationContext",
  );
  return {
    ...actual,
    useNotify: () => ({ notify: notifyMock }),
  };
});

const notifyMock = vi.fn();

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("DownloadPdfButton (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let DownloadPdfButton: typeof import("../DownloadPdfButton").DownloadPdfButton;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    if (!URL.createObjectURL) {
      URL.createObjectURL = vi.fn(() => "blob:mock-url");
    }
    if (!URL.revokeObjectURL) {
      URL.revokeObjectURL = vi.fn();
    }
    ({ render, screen, waitFor, fireEvent } = await import(
      "../../../test/test-utils"
    ));
    ({ DownloadPdfButton } = await import("../DownloadPdfButton"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("happy path → gerçek backend PDF blob indirir, başarı toast'ı gösterilir", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<DownloadPdfButton />);
    fireEvent.click(screen.getByRole("button", { name: /CEO 1-pager/i }));

    await waitFor(
      () =>
        expect(
          screen.getByRole("button", { name: /CEO 1-pager/i }),
        ).not.toBeDisabled(),
      { timeout: 10000 },
    );
    // Regression: indirme öncesi başarılı indirmede HİÇ geri bildirim
    // yoktu (ne toast ne görünür durum değişikliği) — kullanıcı indirmenin
    // başlayıp bittiğini anlayamıyordu.
    expect(notifyMock).toHaveBeenCalledWith("success", expect.any(String));
  }, 15000);
});
