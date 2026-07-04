/**
 * 0-mock epiği: useTripsData.test.tsx'in mock'lu senaryolarına ek olarak,
 * gerçek backend'e karşı çalışan bir sürüm. `tripService` (getAll/getStats/
 * getFuelPerformance/getBeklemede) ve `useTripStore` (gerçek, yerel Zustand
 * state — backend çağrısı değil) MOCK'LANMIYOR; gerçek GET /trips/,
 * /trips/stats, /trips/beklemede çağrıları yapılır.
 *
 * Orijinal mock'lu dosya (useTripsData.test.tsx) korunuyor: KPI kartlarının
 * TAM sayısal değerleri (120 toplam / 95 tamamlanan / 10 iptal / 32.4
 * L/100km ort. tüketim gibi) sabit mock veriye dayanıyor — bu tam sayıları
 * gerçek backend'de üretmek (çok sayıda gerçek sefer + yakıt kaydı seed
 * etmek) bu testin değerine oranla orantısız; formül/format mantığı zaten
 * mock'lu testte doğrulanıyor. Bu dosya bunun yerine gerçek entegrasyonun
 * KENDİSİNİ (fetch/queryKey/pagination/dataUpdatedAt/hasActiveFilter) test
 * ediyor.
 */
import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeAll, afterAll } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import React from "react";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../test/real-backend";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <MemoryRouter>
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    </MemoryRouter>
  );
}

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("useTripsData (real backend)", () => {
  let useTripsData: typeof import("../useTripsData").useTripsData;
  let useTripStore: typeof import("../../stores/use-trip-store").useTripStore;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ useTripsData } = await import("../useTripsData"));
    ({ useTripStore } = await import("../../stores/use-trip-store"));
  }, 20000);

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  async function resetStore() {
    localStorage.clear();
    useTripStore.persist.clearStorage();
    useTripStore.getState().reset();
    await useTripStore.persist.rehydrate();
  }

  it("fetches real trips/stats/beklemede and populates dataUpdatedAt", async () => {
    sessionStorage.setItem("access_token", authToken);
    await resetStore();

    const { result } = renderHook(() => useTripsData(), { wrapper });

    await waitFor(
      () => {
        expect(result.current.dataUpdatedAt).toBeGreaterThan(0);
      },
      { timeout: 10000 },
    );
    // Real backend returns either the empty-stats fallback ([]) or 5 real
    // KPI cards, depending on whether any sefer/fuel data exists — either
    // is a valid outcome, unlike the mocked test's fixed 5-card assertion.
    expect(Array.isArray(result.current.stats)).toBe(true);
    expect(typeof result.current.beklemedeSayisi).toBe("number");
    expect(result.current.beklemedeSayisi).toBeGreaterThanOrEqual(0);
  }, 15000);

  it("derives pagination defaults from the real (empty-filter) query", async () => {
    sessionStorage.setItem("access_token", authToken);
    await resetStore();

    const { result } = renderHook(() => useTripsData(), { wrapper });

    expect(result.current.currentPage).toBe(1);
    expect(result.current.pageSize).toBe(100);
    await waitFor(
      () => {
        expect(result.current.totalPages).toBeGreaterThanOrEqual(1);
      },
      { timeout: 10000 },
    );
  }, 15000);

  it("hasActiveFilter is false with no filters applied against the real store", async () => {
    sessionStorage.setItem("access_token", authToken);
    await resetStore();

    const { result } = renderHook(() => useTripsData(), { wrapper });
    expect(result.current.hasActiveFilter).toBe(false);
  }, 15000);
});
