/**
 * 0-mock epiği: alerts domain. `investigationService.getPatterns`
 * orval-generated client üzerinden gidiyor — baseURL origin-only
 * (REAL_BACKEND_ORIGIN).
 *
 * Orijinal dosyanın "iki pattern → tablo satırlarda görünür" testi, iki
 * mock'lanmış tekrarlayan-örüntü kaydı render ediyordu. Bu, backend'in
 * tekrarlayan şoför/anomali örüntüsü tespiti yapabilmesi için gerçek,
 * birikmiş Anomaly + Investigation geçmişi gerektiriyor — anomaliler
 * ML/RCA pipeline'ı tarafından üretiliyor, frontend'in erişebildiği hiçbir
 * API yüzeyinden create edilemiyor (bkz InvestigationDetailDialog.test.tsx
 * / InvestigationsKanban.test.tsx'teki aynı doküman notu). Bu yüzden "iki
 * pattern" testi gerçek backend'e çevrilemiyor.
 *
 * "boş döndüğünde 'bulunamadı' mesajı" testi ise gerçek backend'in GERÇEK
 * mevcut durumunu yansıtıyor (doğrulandı:
 * `GET /admin/investigations/patterns?days=30&min_count=3&limit=50` → `[]`).
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("PatternList (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let PatternList: typeof import("../PatternList").PatternList;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ PatternList } = await import("../PatternList"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("gerçek backend boş pattern listesi döndürdüğünde 'bulunamadı' mesajı gösterilir", async () => {
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token); // AuthContext'in olası /auth/me 404 temizlemesine karşı
    render(<PatternList />);
    await waitFor(
      () =>
        expect(
          screen.getByText("Tekrarlayan örüntü bulunamadı."),
        ).toBeInTheDocument(),
      { timeout: 10000 },
    );
  }, 15000);
});
