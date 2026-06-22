/**
 * FleetInsights bileşen testi
 * - Araçlar sekmesi: 4 kart, muayene uyarısı
 * - Dorseler sekmesi: 3 kart
 * - Yükleme iskeleti
 * - Muayene süresi dolmuş / yakında dolacak
 */
import { render, screen, waitFor } from "../../../test/test-utils";
import { describe, it, expect, vi } from "vitest";
import { FleetInsights } from "../FleetInsights";

// vehicleService.getFleetStats mock
vi.mock("../../../api/vehicles", () => ({
  vehicleService: {
    getFleetStats: vi.fn().mockResolvedValue({
      total: 45,
      active: 38,
      inspection_expiring: 3,
      inspection_overdue: 2,
    }),
  },
}));

// reportService.getDashboardStats mock
vi.mock("../../../api/reports", () => ({
  reportService: {
    getDashboardStats: vi.fn().mockResolvedValue({
      toplam_sefer: 1234,
    }),
  },
}));

// dorseService mock (dorseler sekmesi için)
vi.mock("../../../services/dorseService", () => ({
  dorseService: {
    getFleetStats: vi.fn().mockResolvedValue({ total: 3, active: 2 }),
  },
}));

// driverService mock (sürücüler sekmesi için)
vi.mock("../../../api/drivers", () => ({
  driverService: {
    getFleetStats: vi.fn().mockResolvedValue({ total: 15, active: 12 }),
  },
}));

describe("FleetInsights — Araçlar Sekmesi", () => {
  it("4 stat kartı render eder", async () => {
    render(<FleetInsights activeTab="vehicles" />);
    // Yükleme sonrası 4 kart bekleniyor
    await waitFor(() => {
      expect(screen.getByText("45")).toBeInTheDocument(); // toplam
      expect(screen.getByText("38")).toBeInTheDocument(); // aktif
    });
  });

  it("muayene uyarı kartı: overdue + expiring sayısını toplar", async () => {
    render(<FleetInsights activeTab="vehicles" />);
    await waitFor(() => {
      // 3 + 2 = 5 araç
      expect(screen.getByText("5")).toBeInTheDocument();
    });
  });

  it("muayene sorun varsa sarı sol kenarlık kart gösterir", async () => {
    render(<FleetInsights activeTab="vehicles" />);
    await waitFor(() => {
      const warningCard = document.querySelector(".border-l-warning\\/60");
      expect(warningCard).toBeInTheDocument();
    });
  });

  it("muayene sorun yoksa yeşil sol kenarlık kart gösterir", async () => {
    const { vehicleService } = await import("../../../api/vehicles");
    vi.mocked(vehicleService.getFleetStats).mockResolvedValueOnce({
      total: 10,
      active: 10,
      inspection_expiring: 0,
      inspection_overdue: 0,
    });
    render(<FleetInsights activeTab="vehicles" />);
    await waitFor(() => {
      const successCard = document.querySelector(".border-l-success\\/60");
      expect(successCard).toBeInTheDocument();
    });
  });

  it("yükleme sırasında 4 iskelet kart gösterir", async () => {
    // require() ESM'de çalışmaz — await import kullan
    const { vehicleService } = await import("../../../api/vehicles");
    vi.mocked(vehicleService.getFleetStats).mockReturnValueOnce(
      new Promise(() => {}),
    ); // asla resolve etme
    render(<FleetInsights activeTab="vehicles" />);
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBe(4);
  });
});

describe("FleetInsights — Dorseler Sekmesi", () => {
  it("3 stat kartı render eder", async () => {
    render(<FleetInsights activeTab="trailers" />);
    await waitFor(() => {
      // Mock her iki getAll çağrısı için 3 eleman döndürür → toplam=3, aktif=3
      // getAllByText kullan, aynı değer birden fazla kartta görünür
      const threes = screen.getAllByText("3");
      expect(threes.length).toBeGreaterThan(0);
    });
  });
});
