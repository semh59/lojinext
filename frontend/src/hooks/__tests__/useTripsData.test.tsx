/**
 * useTripsData hook testi
 * - Stats hesabı (cancelled_count, fallback logic)
 * - beklemedeSayisi hesabı
 * - Pagination türetilen değerler
 * - queryKey bağımsızlığı
 */
import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { useTripsData } from "../useTripsData";

// Servis mock'ları
vi.mock("../../api/trips", () => ({
  tripService: {
    getAll: vi.fn().mockResolvedValue({
      items: [],
      meta: { total: 0, skip: 0, limit: 100 },
    }),
    getStats: vi.fn().mockResolvedValue({
      total_count: 120,
      completed_count: 95,
      cancelled_count: 10,
      total_distance_km: 48000,
      avg_consumption: 32.4,
    }),
    getFuelPerformance: vi.fn().mockResolvedValue([]),
    getBeklemede: vi.fn().mockResolvedValue([
      { id: 1, onay_durumu: "beklemede" },
      { id: 2, onay_durumu: "beklemede" },
    ]),
  },
}));

vi.mock("../../stores/use-trip-store", () => ({
  useTripStore: () => ({
    filters: {
      durum: "",
      search: "",
      baslangic_tarih: "",
      bitis_tarih: "",
      skip: 0,
      limit: 100,
    },
    setFilters: vi.fn(),
    showCharts: false,
  }),
}));

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

describe("useTripsData", () => {
  describe("stats hesabı", () => {
    it("5 KPI kartı döndürür (cancelled_count dahil)", async () => {
      const { result } = renderHook(() => useTripsData(), { wrapper });
      await waitFor(() => expect(result.current.stats.length).toBe(5));
    });

    it("4. eleman (indeks 3) ort. tüketim değerini formatlar", async () => {
      const { result } = renderHook(() => useTripsData(), { wrapper });
      await waitFor(() => expect(result.current.stats.length).toBe(5));
      const tuketimKart = result.current.stats[3];
      expect(tuketimKart.label).toBe("Ort. Tüketim");
      expect(tuketimKart.value).toBe("32.4");
      expect(tuketimKart.unit).toBe("L/100km");
    });

    it("5. eleman (indeks 4) iptal sayısını gösterir", async () => {
      const { result } = renderHook(() => useTripsData(), { wrapper });
      await waitFor(() => expect(result.current.stats.length).toBe(5));
      const iptalKart = result.current.stats[4];
      expect(iptalKart.value).toBe(10);
    });

    it("stats yokken boş dizi döner", async () => {
      const { tripService } = await import("../../api/trips");
      vi.mocked(tripService.getStats).mockResolvedValueOnce(undefined as any);
      vi.mocked(tripService.getStats).mockResolvedValueOnce(undefined as any);
      const { result } = renderHook(() => useTripsData(), { wrapper });
      // Başlangıçta boş
      expect(result.current.stats).toEqual([]);
    });
  });

  describe("beklemedeSayisi", () => {
    it("beklemede sayısını doğru hesaplar", async () => {
      const { result } = renderHook(() => useTripsData(), { wrapper });
      await waitFor(() => expect(result.current.beklemedeSayisi).toBe(2));
    });

    it("beklemede boş gelince 0 döner", async () => {
      const { tripService } = await import("../../api/trips");
      vi.mocked(tripService.getBeklemede).mockResolvedValueOnce([]);
      const { result } = renderHook(() => useTripsData(), { wrapper });
      await waitFor(() => {
        // Sonuç geldi mi bekle
        expect(result.current.dataUpdatedAt).toBeDefined();
      });
      expect(result.current.beklemedeSayisi).toBe(0);
    });
  });

  describe("pagination türetilen değerler", () => {
    it("currentPage 1 olarak başlar (skip=0)", async () => {
      const { result } = renderHook(() => useTripsData(), { wrapper });
      expect(result.current.currentPage).toBe(1);
    });

    it("totalPages en az 1 döner", async () => {
      const { result } = renderHook(() => useTripsData(), { wrapper });
      expect(result.current.totalPages).toBeGreaterThanOrEqual(1);
    });

    it("pageSize limit parametresinden türetilir", async () => {
      const { result } = renderHook(() => useTripsData(), { wrapper });
      expect(result.current.pageSize).toBe(100);
    });
  });

  describe("dataUpdatedAt", () => {
    it("query sonrası dataUpdatedAt doldurulur", async () => {
      const { result } = renderHook(() => useTripsData(), { wrapper });
      await waitFor(() =>
        expect(result.current.dataUpdatedAt).toBeGreaterThan(0),
      );
    });
  });

  describe("hasActiveFilter", () => {
    it("filtreler boşken false döner", () => {
      const { result } = renderHook(() => useTripsData(), { wrapper });
      expect(result.current.hasActiveFilter).toBe(false);
    });
  });
});
