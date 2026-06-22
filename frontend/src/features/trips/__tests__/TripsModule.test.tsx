import { beforeEach, describe, expect, it, vi } from "vitest";

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
import { TripsModule } from "../TripsModule";

vi.mock("../../../api/trips");
vi.mock("../../../services/api");
vi.mock("../../../services/dorseService");
vi.mock("../../../api/preferences");

vi.mock("../../../components/ui/Modal", () => ({
  Modal: ({ children, isOpen, title }: any) =>
    isOpen ? (
      <div role="dialog" aria-label={title || "modal"}>
        <h2>{title}</h2>
        {children}
      </div>
    ) : null,
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    loading: vi.fn(),
  },
}));

vi.mock("framer-motion", () => ({
  motion: new Proxy(
    {},
    {
      get: (_target, key: string) => {
        const tag =
          key === "tr"
            ? "tr"
            : key === "span"
              ? "span"
              : key === "p"
                ? "p"
                : "div";
        return ({ children, ...props }: any) => {
          const Tag = tag as keyof JSX.IntrinsicElements;
          return <Tag {...props}>{children}</Tag>;
        };
      },
    },
  ),
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

describe("TripsModule Integration Tests", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    localStorage.clear();
    useTripStore.persist.clearStorage();
    useTripStore.getState().reset();
    await useTripStore.persist.rehydrate();

    vi.mocked(tripService.getStats).mockResolvedValue({
      total_count: 0,
      completed_count: 0,
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
    vi.mocked(tripService.getAll).mockResolvedValue({
      items: [],
      meta: { total: 0, skip: 0, limit: 100 },
    });
    vi.mocked(vehiclesApi.getAll).mockResolvedValue({
      items: [{ id: 1, plaka: "34ABC123", marka: "Test", model: "X" }] as any,
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

  it("renders core header actions", async () => {
    render(<TripsModule />);

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: /sefer yönetimi/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/yakıt performansı/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /yeni sefer oluştur/i }),
    ).toBeInTheDocument();
  });

  it("opens modal when clicking create button", async () => {
    render(<TripsModule />);

    const createButton = await screen.findByRole("button", {
      name: /yeni sefer oluştur/i,
    });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(useTripStore.getState().isFormOpen).toBe(true);
    });
  });

  it("calls trip list service on mount", async () => {
    render(<TripsModule />);

    await waitFor(() => {
      expect(tripService.getAll).toHaveBeenCalled();
    });
  });

  it("shows error panel when list request fails", async () => {
    vi.mocked(tripService.getAll).mockRejectedValueOnce({
      response: { status: 500 },
    });
    render(<TripsModule />);

    expect(await screen.findByText("Veri Yüklenemedi")).toBeInTheDocument();
    expect(
      screen.getByText(/lütfen internet bağlantınızı kontrol/i),
    ).toBeInTheDocument();
  });

  it("opens fuel performance panel", async () => {
    render(<TripsModule />);

    const toggle = await screen.findByText(/yakıt performansı/i);
    fireEvent.click(toggle);

    expect(await screen.findByText(/paneli kapat/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(tripService.getFuelPerformance).toHaveBeenCalled();
    });
  });
});
