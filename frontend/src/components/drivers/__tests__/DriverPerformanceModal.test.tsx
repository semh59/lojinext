import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";
import { DriverPerformanceModal } from "../DriverPerformanceModal";
import { driverPerformanceText } from "../../../resources/tr/drivers";
import { Driver } from "../../../types";

// framer-motion passthrough
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, className, ...rest }: any) => (
      <div className={className} {...rest}>
        {children}
      </div>
    ),
  },
}));

// Mock driver service
vi.mock("../../../api/drivers", () => ({
  driverService: {
    getPerformance: vi.fn(),
    getScoreBreakdown: vi.fn(),
    getRouteProfile: vi.fn(),
  },
}));

// Mock sub-components that make additional API calls
vi.mock("../DriverScoreBreakdown", () => ({
  DriverScoreBreakdown: () => (
    <div data-testid="score-breakdown">Skor Detayı İçeriği</div>
  ),
}));

vi.mock("../DriverRouteProfile", () => ({
  DriverRouteProfile: () => (
    <div data-testid="route-profile">Güzergah Profili İçeriği</div>
  ),
}));

const MOCK_DRIVER: Driver = {
  id: 7,
  ad_soyad: "Ahmet Yılmaz",
  telefon: "0532 111 22 33",
  ehliyet_sinifi: "CE",
  aktif: true,
  manual_score: 1.5,
  score: 1.5,
};

const MOCK_PERFORMANCE = {
  safety_score: 85,
  eco_score: 78,
  compliance_score: 90,
  total_score: 84,
  trend: "increasing" as const,
  total_km: 52000,
  total_trips: 47,
};

describe("DriverPerformanceModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when isOpen=false", () => {
    render(
      <DriverPerformanceModal
        isOpen={false}
        onClose={vi.fn()}
        driver={MOCK_DRIVER}
      />,
    );
    expect(
      screen.queryByText(driverPerformanceText.title),
    ).not.toBeInTheDocument();
  });

  it("shows modal title and driver name in subtitle", async () => {
    const { driverService } = await import("../../../api/drivers");
    (
      driverService.getPerformance as ReturnType<typeof vi.fn>
    ).mockResolvedValue(MOCK_PERFORMANCE);

    render(
      <DriverPerformanceModal
        isOpen={true}
        onClose={vi.fn()}
        driver={MOCK_DRIVER}
      />,
    );

    expect(screen.getByText(driverPerformanceText.title)).toBeInTheDocument();
    expect(
      screen.getByText(driverPerformanceText.subtitle(MOCK_DRIVER.ad_soyad)),
    ).toBeInTheDocument();
  });

  it("shows loading indicator while fetching", async () => {
    const { driverService } = await import("../../../api/drivers");
    // Never resolves — stays in loading state
    (driverService.getPerformance as ReturnType<typeof vi.fn>).mockReturnValue(
      new Promise(() => {}),
    );

    render(
      <DriverPerformanceModal
        isOpen={true}
        onClose={vi.fn()}
        driver={MOCK_DRIVER}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByText(driverPerformanceText.loading),
      ).toBeInTheDocument();
    });
  });

  it("shows total score, safety, eco, and compliance scores on success", async () => {
    const { driverService } = await import("../../../api/drivers");
    (
      driverService.getPerformance as ReturnType<typeof vi.fn>
    ).mockResolvedValue(MOCK_PERFORMANCE);

    render(
      <DriverPerformanceModal
        isOpen={true}
        onClose={vi.fn()}
        driver={MOCK_DRIVER}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByText(driverPerformanceText.totalScore),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("84")).toBeInTheDocument();
    expect(
      screen.getByText(driverPerformanceText.cards.safety),
    ).toBeInTheDocument();
    expect(
      screen.getByText(driverPerformanceText.cards.eco),
    ).toBeInTheDocument();
    expect(
      screen.getByText(driverPerformanceText.cards.compliance),
    ).toBeInTheDocument();
    expect(
      screen.getByText(driverPerformanceText.trends.increasing),
    ).toBeInTheDocument();
  });

  it("shows stats: trip count and total km", async () => {
    const { driverService } = await import("../../../api/drivers");
    (
      driverService.getPerformance as ReturnType<typeof vi.fn>
    ).mockResolvedValue(MOCK_PERFORMANCE);

    render(
      <DriverPerformanceModal
        isOpen={true}
        onClose={vi.fn()}
        driver={MOCK_DRIVER}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("47")).toBeInTheDocument();
    });
    expect(screen.getByText("52000")).toBeInTheDocument();
    expect(
      screen.getByText(driverPerformanceText.stats.trips),
    ).toBeInTheDocument();
    expect(
      screen.getByText(driverPerformanceText.stats.distance),
    ).toBeInTheDocument();
  });

  it("shows error fallback when API call fails", async () => {
    const { driverService } = await import("../../../api/drivers");
    (
      driverService.getPerformance as ReturnType<typeof vi.fn>
    ).mockRejectedValue(new Error("network error"));

    render(
      <DriverPerformanceModal
        isOpen={true}
        onClose={vi.fn()}
        driver={MOCK_DRIVER}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByText(driverPerformanceText.errorFallback),
      ).toBeInTheDocument();
    });
  });

  it("renders three tabs", async () => {
    const { driverService } = await import("../../../api/drivers");
    (
      driverService.getPerformance as ReturnType<typeof vi.fn>
    ).mockResolvedValue(MOCK_PERFORMANCE);

    render(
      <DriverPerformanceModal
        isOpen={true}
        onClose={vi.fn()}
        driver={MOCK_DRIVER}
      />,
    );

    expect(
      screen.getByText(driverPerformanceText.tabs.performance),
    ).toBeInTheDocument();
    expect(
      screen.getByText(driverPerformanceText.tabs.breakdown),
    ).toBeInTheDocument();
    expect(
      screen.getByText(driverPerformanceText.tabs.routes),
    ).toBeInTheDocument();
  });
});
