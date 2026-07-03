/**
 * 0-mock epiği: alerts domain. `investigationService.list` orval-generated
 * client üzerinden gidiyor — baseURL origin-only (REAL_BACKEND_ORIGIN).
 *
 * Orijinal dosyanın "iki kart farklı kolonlarda görünür" testi, iki
 * mock'lanmış Investigation kaydı render ediyordu. Gerçek backend'de bir
 * investigation açmak önce gerçek bir Anomaly kaydı gerektiriyor (bkz
 * InvestigationDetailDialog.test.tsx'teki doküman notu — `anomaly_id` FK
 * kontrolü, anomaliler yalnızca ML/RCA pipeline'ı tarafından üretiliyor,
 * frontend API yüzeyinden create edilemiyor). Bu yüzden "iki kart" testi
 * gerçek backend'e çevrilemiyor.
 *
 * "boş liste → emptyKanban mesajı" testi ise gerçek backend'in GERÇEK
 * mevcut durumunu yansıtıyor — bu backend'de hâlâ hiç investigation kaydı
 * yok (doğrulandı: `GET /admin/investigations?days=30&limit=200` → `[]`),
 * bu yüzden gerçek bir HTTP round-trip ile aynen doğrulanabiliyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import type { ReactElement } from "react";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("InvestigationsKanban (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let InvestigationsKanban: typeof import("../InvestigationsKanban").InvestigationsKanban;
  let NotificationProvider: typeof import("../../../context/NotificationContext").NotificationProvider;

  // InvestigationsKanban dahili olarak InvestigationDetailDialog render
  // ediyor, o da gerçek `useNotify()` çağırıyor (mock yok) — test-utils.tsx
  // NotificationProvider'ı sarmadığı için burada elle sarmalıyoruz (bkz
  // InvestigationDetailDialog.test.tsx'teki aynı not).
  const renderWithNotify = (ui: ReactElement) =>
    render(<NotificationProvider>{ui}</NotificationProvider>);

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ InvestigationsKanban } = await import("../InvestigationsKanban"));
    ({ NotificationProvider } = await import(
      "../../../context/NotificationContext"
    ));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("gerçek backend boş investigation listesi döndürdüğünde emptyKanban mesajı gösterilir", async () => {
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token); // AuthContext'in olası /auth/me 404 temizlemesine karşı
    renderWithNotify(<InvestigationsKanban />);
    await waitFor(
      () =>
        expect(screen.getByText("Henüz soruşturma yok.")).toBeInTheDocument(),
      { timeout: 10000 },
    );
  }, 15000);
});
