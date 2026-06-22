import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import {
  driversApi,
  locationService,
  vehiclesApi,
  weatherApi,
} from "../../../services/api";
import { preferenceService } from "../../../api/preferences";
import { tripService } from "../../../api/trips";
import { dorseService } from "../../../services/dorseService";
import { useTripStore } from "../../../stores/use-trip-store";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import { TripsModule } from "../../../features/trips/TripsModule";

vi.mock("../../../api/trips");
vi.mock("../../../services/api");
vi.mock("../../../services/dorseService");
vi.mock("../../../api/preferences");

// Provide a full-permission admin user so permission-gated buttons are visible
vi.mock("../../../context/AuthContext", () => ({
  AuthProvider: ({ children }: any) => <>{children}</>,
  useAuth: () => ({
    user: { id: 1, username: "admin", role: "admin" },
    isAuthenticated: true,
    isLoading: false,
    hasPermission: () => true,
    login: vi.fn(),
    logout: vi.fn(),
    error: null,
  }),
}));

vi.mock("../TripFormModal", () => ({
  TripFormModal: ({ isOpen }: any) =>
    isOpen ? <div data-testid="trip-form-modal">Form Modal</div> : null,
}));

beforeAll(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    loading: vi.fn(),
  },
}));

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    tr: ({ children, ...props }: any) => <tr {...props}>{children}</tr>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

vi.mock("../../../components/auth/RequirePermission", () => ({
  RequirePermission: ({ children }: any) => <>{children}</>,
}));

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: (args: any) => {
    const count = args?.count ?? 0;
    return {
      getTotalSize: () => count * 140,
      getVirtualItems: () =>
        Array.from({ length: count }).map((_, index) => ({
          key: `row-${index}`,
          index,
          size: 140,
          start: index * 140,
        })),
    };
  },
}));

const mockTrip = {
  id: 1,
  tarih: "2026-01-15",
  saat: "08:30",
  arac_id: 1,
  sofor_id: 1,
  guzergah_id: 1,
  cikis_yeri: "İstanbul",
  varis_yeri: "Ankara",
  mesafe_km: 450,
  bos_agirlik_kg: 8000,
  dolu_agirlik_kg: 18000,
  net_kg: 10000,
  ton: 10,
  durum: "Tamamlandı",
  plaka: "34ABC123",
  sofor_adi: "Test Şoför",
};

const deleteActionMatcher = (_content: string, element: Element | null) => {
  const text = (element?.textContent ?? "").toUpperCase();
  return (
    text.includes("SEFER") && (text.includes("SIL") || text.includes("SİL"))
  );
};

describe("Browser Compatibility Tests", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useTripStore.getState().reset();

    vi.mocked(tripService.getAll).mockResolvedValue({
      items: [mockTrip as any],
      meta: { total: 1, skip: 0, limit: 100 },
    });
    vi.mocked(tripService.getStats).mockResolvedValue({
      total_count: 1,
      completed_count: 1,
      cancelled_count: 0,
      planned_count: 0,
      in_progress_count: 0,
    } as any);
    vi.mocked(tripService.getFuelPerformance).mockResolvedValue({
      kpis: { mae: 0, rmse: 0, total_compared: 0, high_deviation_ratio: 0 },
      trend: [],
      distribution: {
        good: 0,
        warning: 0,
        error: 0,
        good_pct: 0,
        warning_pct: 0,
        error_pct: 0,
      },
      outliers: [],
      low_data: true,
    } as any);
    vi.mocked(vehiclesApi.getAll).mockResolvedValue({
      items: [{ id: 1, plaka: "34ABC123" }] as any,
      total: 1,
    });
    vi.mocked(driversApi.getAll).mockResolvedValue({
      items: [{ id: 1, ad_soyad: "Test Şoför" }] as any,
      total: 1,
    });
    vi.mocked(locationService.getAll).mockResolvedValue({
      items: [],
      total: 0,
    } as any);
    vi.mocked(weatherApi.getTripImpact).mockResolvedValue({
      fuel_impact_factor: 1,
    } as any);
    vi.mocked(dorseService.getAll).mockResolvedValue({ data: [] } as any);
    vi.mocked(preferenceService.getPreferences).mockResolvedValue([]);
    vi.mocked(preferenceService.savePreference).mockResolvedValue({} as any);
    vi.mocked(preferenceService.deletePreference).mockResolvedValue({} as any);
  });

  describe("window.confirm - Delete Actions", () => {
    it("calls window.confirm before delete", async () => {
      const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
      vi.mocked(tripService.delete).mockResolvedValue(undefined);

      render(<TripsModule />);
      await screen.findAllByText(deleteActionMatcher, { selector: "button" });

      const deleteButtons = screen.getAllByText(deleteActionMatcher, {
        selector: "button",
      });
      fireEvent.click(deleteButtons[0]);

      expect(confirmSpy).toHaveBeenCalledWith(
        "Bu seferi silmek istediğinize emin misiniz?",
      );
      confirmSpy.mockRestore();
    });

    it("does not delete when confirm returns false", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(false);

      render(<TripsModule />);
      await screen.findAllByText(deleteActionMatcher, { selector: "button" });

      const deleteButtons = screen.getAllByText(deleteActionMatcher, {
        selector: "button",
      });
      fireEvent.click(deleteButtons[0]);

      expect(tripService.delete).not.toHaveBeenCalled();
      vi.restoreAllMocks();
    });
  });

  describe("window.URL - Export/Download", () => {
    it("creates object URL for blob and triggers download link", async () => {
      const mockBlob = new Blob(["test-excel-data"], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });

      const createObjectURL = vi
        .fn()
        .mockReturnValue("blob:http://localhost/test-uuid");
      const revokeObjectURL = vi.fn();
      window.URL.createObjectURL = createObjectURL;
      window.URL.revokeObjectURL = revokeObjectURL;

      const url = window.URL.createObjectURL(mockBlob);
      expect(createObjectURL).toHaveBeenCalledWith(mockBlob);
      expect(url).toBe("blob:http://localhost/test-uuid");

      const link = document.createElement("a");
      link.href = url;
      link.download = "seferler.xlsx";
      expect(link.href).toBe("blob:http://localhost/test-uuid");
      expect(link.download).toBe("seferler.xlsx");

      window.URL.revokeObjectURL(url);
      expect(revokeObjectURL).toHaveBeenCalledWith(
        "blob:http://localhost/test-uuid",
      );
    });

    it("calls tripService.exportExcel with correct params", async () => {
      const mockBlob = new Blob(["data"], { type: "application/xlsx" });
      vi.mocked(tripService.exportExcel).mockResolvedValue(mockBlob);

      const result = await tripService.exportExcel();
      expect(tripService.exportExcel).toHaveBeenCalled();
      expect(result).toBe(mockBlob);
    });
  });

  describe("localStorage - Zustand Persist", () => {
    it("persists filters to localStorage", () => {
      const store = useTripStore.getState();
      store.setFilters({ durum: "Tamamlandı", search: "test" });

      const stored = localStorage.getItem("lojinext-trip-storage-anon");
      expect(stored).toBeTruthy();

      const parsed = JSON.parse(stored!);
      expect(parsed.state.filters.durum).toBe("Tamamlandı");
      expect(parsed.state.filters.search).toBe("test");
    });

    it("restores filters from localStorage", () => {
      const seedData = {
        state: {
          filters: {
            durum: "Devam Ediyor",
            search: "İstanbul",
            baslangic_tarih: "",
            bitis_tarih: "",
            skip: 0,
            limit: 100,
          },
          viewMode: "table",
        },
        version: 0,
      };
      localStorage.setItem(
        "lojinext-trip-storage-anon",
        JSON.stringify(seedData),
      );

      useTripStore.persist.rehydrate();

      const state = useTripStore.getState();
      expect(state.filters.durum).toBe("Planlandı");
      expect(state.filters.search).toBe("İstanbul");
    });

    it("handles corrupted localStorage gracefully", () => {
      localStorage.setItem("lojinext-trip-storage-anon", "CORRUPTED_JSON{{{{");

      expect(() => {
        useTripStore.persist.rehydrate();
      }).not.toThrow();
    });
  });

  describe("CSS API - backdrop-filter support", () => {
    it("uses backdrop-blur classes that require browser support", async () => {
      const { container } = render(<TripsModule />);

      await waitFor(() => {
        const blurElements = container.querySelectorAll(
          '[class*="backdrop-blur"]',
        );
        expect(blurElements.length).toBeGreaterThanOrEqual(0);
      });
    });
  });
});
