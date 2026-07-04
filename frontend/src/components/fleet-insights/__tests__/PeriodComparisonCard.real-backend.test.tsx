/**
 * 0-mock epiği: PeriodComparisonCard.test.tsx'in mock'lu senaryolarına ek
 * olarak, gerçek backend'e karşı seed gerektirmeyen senaryolar.
 *
 * Backend endpoint gerçek path'i `/api/v1/reports/insights/fleet/comparison`
 * (bkz app/api/v1/api.py:135-139 — prefix `/reports/insights/fleet` +
 * endpoint path `/comparison`). curl ile doğrulandı, GET
 * `/reports/insights/fleet-comparison` DEĞİL (o path 404 döner).
 *
 * Boş test DB'sinde tüm metrikler 0, tüm delta_pct null döner → "Veri yok"
 * senaryosu (mock'lu dosyadaki 2. test ile birebir eşleşen davranış) gerçek
 * backend'den deterministik olarak üretilebiliyor.
 *
 * Happy-path (non-null delta_pct, örn. -9.1%) gerçek DB'de haftalar arası
 * seed edilmiş sefer+yakıt verisi gerektirir — bu 3 dosyalık görev kapsamı
 * dışında; o senaryo mock'lu dosyada kalıyor.
 *
 * Hata senaryosu: geçersiz `period` query param'ı backend'in gerçek
 * literal-validation'ını (422) tetikler → react-query error state → "yüklenemedi"
 * mesajı. Bileşen normalde period="week"|"month" tipiyle kısıtlı olduğu için
 * burada `as any` ile bypass ediyoruz (curl ile 422 doğrulandı).
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("PeriodComparisonCard (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let PeriodComparisonCard: typeof import("../PeriodComparisonCard").PeriodComparisonCard;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ PeriodComparisonCard } = await import("../PeriodComparisonCard"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it('boş test DB → tüm metrikler "Veri yok" gösterir (week)', async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<PeriodComparisonCard period="week" />);

    await waitFor(() => screen.getByText(/Bu Hafta vs Geçen/), {
      timeout: 10000,
    });
    await waitFor(
      () =>
        expect(screen.getAllByText("Veri yok").length).toBeGreaterThanOrEqual(
          4,
        ),
      { timeout: 10000 },
    );
  }, 15000);

  it('boş test DB → tüm metrikler "Veri yok" gösterir (month)', async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<PeriodComparisonCard period="month" />);

    await waitFor(() => screen.getByText(/Bu Ay vs Geçen/), {
      timeout: 10000,
    });
    await waitFor(
      () =>
        expect(screen.getAllByText("Veri yok").length).toBeGreaterThanOrEqual(
          4,
        ),
      { timeout: 10000 },
    );
  }, 15000);

  it("gerçek 422 (geçersiz period) → yüklenemedi mesajı", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<PeriodComparisonCard period={"bogus" as never} />);

    await waitFor(
      () =>
        expect(
          screen.getByText(/Karşılaştırma yüklenemedi/),
        ).toBeInTheDocument(),
      { timeout: 10000 },
    );
  }, 15000);
});
