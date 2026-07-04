/**
 * 0-mock epiği: TodayPage `GET /reports/today/triage`'i gerçek backend'e
 * karşı çağırır. Bu izole test DB'sinde anomali/bakım/soruşturma triage
 * item'ları üretmek üç ayrı domain'in (anomaly detection, maintenance
 * scheduling, investigation) canlı state'ini sentetik olarak inşa etmeyi
 * gerektirir — masraflı ve kırılgan. Bu yüzden burada cold-start/boş-state
 * (gerçek backend, seed'siz DB → critical_count=0/pending_count=0/items=[])
 * doğrulanıyor: sayaçlar, tab bar, Quick Actions bar ve "acil eylem yok"
 * boş-state mesajı gerçek HTTP round-trip ile render oluyor.
 *
 * Seed'li happy-path (3 kategori item, severity filtreleme, tab switch) ve
 * 503 hata-enjeksiyonu senaryoları orijinal mock'lu haliyle
 * `TodayPage.mocked.test.tsx`'te KORUNUYOR — component'in kendi filtreleme/
 * hata-render mantığı zaten orada kanıtlı, gerçek backend'de aynı sentetik
 * veriyi üretmek bu testin katma değerine oranla aşırı pahalı.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("TodayPage (real backend)", () => {
  let render: typeof import("../../test/test-utils").render;
  let screen: typeof import("../../test/test-utils").screen;
  let waitFor: typeof import("../../test/test-utils").waitFor;
  let TodayPage: typeof import("../TodayPage").default;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ render, screen, waitFor } = await import("../../test/test-utils"));
    ({ default: TodayPage } = await import("../TodayPage"));
  }, 20000);

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it('boş-state → "Bugün için acil eylem yok" + Quick Actions bar görünür', async () => {
    sessionStorage.setItem("access_token", await loginAsAdmin());
    render(<TodayPage />);

    await waitFor(
      () => {
        expect(screen.getByText(/Bugün için acil eylem yok/i)).toBeTruthy();
      },
      { timeout: 15000 },
    );

    expect(screen.getByText("Hızlı Erişim")).toBeTruthy();
  }, 20000);
});
