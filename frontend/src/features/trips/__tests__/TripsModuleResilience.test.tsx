import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../../../context/AuthContext";

import { TripsModule } from "../TripsModule";
import {
  driversApi,
  locationService,
  vehiclesApi,
  weatherApi,
} from "../../../services/api";
import { preferenceService } from "../../../api/preferences";
import { tripService } from "../../../api/trips";
import { dorseService } from "../../../services/dorseService";

vi.mock("../../../api/trips");
vi.mock("../../../services/api");
vi.mock("../../../services/dorseService");
vi.mock("../../../api/preferences");

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

const renderWithClient = (ui: React.ReactNode) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter>{ui}</MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
};

describe("TripsModule Resilience Tests", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
    vi.mocked(vehiclesApi.getAll).mockResolvedValue({ items: [], total: 0 });
    vi.mocked(driversApi.getAll).mockResolvedValue({ items: [], total: 0 });
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

  it("displays loading skeleton when fetching data", async () => {
    vi.mocked(tripService.getAll).mockImplementation(
      () => new Promise(() => {}),
    );

    renderWithClient(<TripsModule />);

    await waitFor(() => {
      const loadingElements = document.getElementsByClassName("skeleton");
      expect(loadingElements.length).toBeGreaterThan(0);
    });
  });

  it("displays error UI when API fails", async () => {
    vi.mocked(tripService.getAll).mockRejectedValue(new Error("Network Error"));

    renderWithClient(<TripsModule />);

    expect(await screen.findByText(/veri yüklenemedi/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /yeniden dene/i }),
    ).toBeInTheDocument();
  });

  it("displays empty state when no trips returned", async () => {
    vi.mocked(tripService.getAll).mockResolvedValue({
      items: [],
      meta: { total: 0, skip: 0, limit: 100 },
    });

    renderWithClient(<TripsModule />);

    expect(
      await screen.findByRole("heading", { name: /henüz sefer yok/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/aktif operasyonel sefer bulunmuyor/i),
    ).toBeInTheDocument();
  });

  it('recovers from error when "Yeniden Dene" is clicked', async () => {
    vi.mocked(tripService.getAll).mockRejectedValueOnce(new Error("Fail 1"));

    renderWithClient(<TripsModule />);

    expect(await screen.findByText(/veri yüklenemedi/i)).toBeInTheDocument();

    vi.mocked(tripService.getAll).mockResolvedValue({
      items: [],
      meta: { total: 0, skip: 0, limit: 100 },
    });

    fireEvent.click(screen.getByRole("button", { name: /yeniden dene/i }));

    expect(
      await screen.findByRole("heading", { name: /henüz sefer yok/i }),
    ).toBeInTheDocument();
  });

  it("renders pagination safely when limit becomes invalid", async () => {
    vi.mocked(tripService.getAll).mockResolvedValue({
      items: [
        {
          id: 1,
          tarih: "2026-01-01",
          saat: "10:00",
          arac_id: 1,
          sofor_id: 1,
          guzergah_id: 1,
          cikis_yeri: "A",
          varis_yeri: "B",
          mesafe_km: 100,
          bos_agirlik_kg: 8000,
          dolu_agirlik_kg: 18000,
          net_kg: 10000,
          ton: 10,
          durum: "Tamamlandı",
        },
      ],
      meta: { total: 1, skip: 0, limit: 0 as any },
    } as any);

    renderWithClient(<TripsModule />);

    expect(await screen.findByText(/1 \/ 1/i)).toBeInTheDocument();
  });
});
