import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import AdminMaintenancePage from "../BakimPage";
import { adminMaintenanceText } from "../../../resources/tr/admin";
import { maintenancePredictionsText } from "../../../resources/tr/maintenancePredictions";

// Mock admin-service
vi.mock("../../../api/admin", () => ({
  adminMaintenanceApi: {
    getAlerts: vi.fn(),
    markComplete: vi.fn(),
  },
}));

// Mock notification context
vi.mock("../../../context/NotificationContext", () => ({
  useNotify: () => ({ notify: vi.fn() }),
  NotificationProvider: ({ children }: any) => <>{children}</>,
}));

// Mock usePageTitle
vi.mock("../../../hooks/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

// Mock child sub-components to avoid deep dependency chains
vi.mock("../../../components/admin/maintenance/PredictionsTable", () => ({
  PredictionsTable: () => (
    <div data-testid="predictions-table">PredictionsTable</div>
  ),
}));
vi.mock("../../../components/admin/maintenance/MaintenanceCalendar", () => ({
  MaintenanceCalendar: () => (
    <div data-testid="maintenance-calendar">MaintenanceCalendar</div>
  ),
}));

const MOCK_ALERTS = [
  {
    id: 1,
    arac_id: 10,
    bakim_tipi: "YAG_DEGISIMI",
    bakim_tarihi: "2026-06-10T00:00:00Z",
    km_bilgisi: 150000,
    durum: "yaklasiyor",
  },
  {
    id: 2,
    arac_id: 11,
    bakim_tipi: "FREN_KONTROLU",
    bakim_tarihi: "2026-05-01T00:00:00Z",
    km_bilgisi: null,
    durum: "gecikmis",
  },
];

describe("AdminMaintenancePage (BakimPage)", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const { adminMaintenanceApi } = await import("../../../api/admin");
    (
      adminMaintenanceApi.getAlerts as ReturnType<typeof vi.fn>
    ).mockResolvedValue(MOCK_ALERTS);
  });

  it("renders page heading", async () => {
    render(<AdminMaintenancePage />);
    expect(screen.getByText(adminMaintenanceText.heading)).toBeInTheDocument();
  });

  it("renders page description", async () => {
    render(<AdminMaintenancePage />);
    expect(
      screen.getByText(adminMaintenanceText.description),
    ).toBeInTheDocument();
  });

  it("renders tab switcher with three tabs", async () => {
    render(<AdminMaintenancePage />);
    expect(
      screen.getByText(maintenancePredictionsText.tabs.history),
    ).toBeInTheDocument();
    expect(
      screen.getByText(maintenancePredictionsText.tabs.list),
    ).toBeInTheDocument();
    expect(
      screen.getByText(maintenancePredictionsText.tabs.calendar),
    ).toBeInTheDocument();
  });

  it("shows history tab content by default (section title visible)", async () => {
    render(<AdminMaintenancePage />);
    expect(
      screen.getByText(adminMaintenanceText.sectionTitle),
    ).toBeInTheDocument();
  });

  it("shows maintenance alerts after loading", async () => {
    render(<AdminMaintenancePage />);
    await waitFor(() => {
      expect(screen.getByText("Araç #10")).toBeInTheDocument();
      expect(screen.getByText("Araç #11")).toBeInTheDocument();
    });
  });

  it("shows maintenance type values", async () => {
    render(<AdminMaintenancePage />);
    await waitFor(() => {
      expect(screen.getByText("YAG_DEGISIMI")).toBeInTheDocument();
      expect(screen.getByText("FREN_KONTROLU")).toBeInTheDocument();
    });
  });

  it("shows status badge for overdue alert", async () => {
    render(<AdminMaintenancePage />);
    await waitFor(() => {
      expect(
        screen.getByText(adminMaintenanceText.statusLabels.overdue),
      ).toBeInTheDocument();
    });
  });

  it("shows status badge for upcoming alert", async () => {
    render(<AdminMaintenancePage />);
    await waitFor(() => {
      expect(
        screen.getByText(adminMaintenanceText.statusLabels.upcoming),
      ).toBeInTheDocument();
    });
  });

  it("shows km info when present", async () => {
    render(<AdminMaintenancePage />);
    await waitFor(() => {
      expect(screen.getByText(/150000 KM/)).toBeInTheDocument();
    });
  });

  it("shows complete action buttons", async () => {
    render(<AdminMaintenancePage />);
    await waitFor(() =>
      expect(screen.getByText("Araç #10")).toBeInTheDocument(),
    );
    const completeBtns = screen.getAllByText(
      adminMaintenanceText.completeAction,
    );
    expect(completeBtns.length).toBe(2);
  });

  it("calls markComplete when complete button clicked", async () => {
    const { adminMaintenanceApi } = await import("../../../api/admin");
    (
      adminMaintenanceApi.markComplete as ReturnType<typeof vi.fn>
    ).mockResolvedValue({});
    render(<AdminMaintenancePage />);
    await waitFor(() =>
      expect(screen.getByText("Araç #10")).toBeInTheDocument(),
    );
    const completeBtns = screen.getAllByText(
      adminMaintenanceText.completeAction,
    );
    fireEvent.click(completeBtns[0]);
    await waitFor(() => {
      expect(adminMaintenanceApi.markComplete).toHaveBeenCalledTimes(1);
      // React Query passes (variable, context) to mutationFn
      expect(
        (adminMaintenanceApi.markComplete as ReturnType<typeof vi.fn>).mock
          .calls[0][0],
      ).toBe(1);
    });
  });

  it("shows empty state when no alerts", async () => {
    const { adminMaintenanceApi } = await import("../../../api/admin");
    (
      adminMaintenanceApi.getAlerts as ReturnType<typeof vi.fn>
    ).mockResolvedValue([]);
    render(<AdminMaintenancePage />);
    await waitFor(() => {
      expect(screen.getByText(adminMaintenanceText.empty)).toBeInTheDocument();
    });
  });

  it("switches to predictions tab and shows PredictionsTable", async () => {
    render(<AdminMaintenancePage />);
    const predictionsTab = screen.getByText(
      maintenancePredictionsText.tabs.list,
    );
    fireEvent.click(predictionsTab);
    await waitFor(() => {
      expect(screen.getByTestId("predictions-table")).toBeInTheDocument();
    });
    // history table section should be gone
    expect(
      screen.queryByText(adminMaintenanceText.sectionTitle),
    ).not.toBeInTheDocument();
  });

  it("switches to calendar tab and shows MaintenanceCalendar", async () => {
    render(<AdminMaintenancePage />);
    const calendarTab = screen.getByText(
      maintenancePredictionsText.tabs.calendar,
    );
    fireEvent.click(calendarTab);
    await waitFor(() => {
      expect(screen.getByTestId("maintenance-calendar")).toBeInTheDocument();
    });
  });

  it("renders table headers in history view", async () => {
    render(<AdminMaintenancePage />);
    await waitFor(() =>
      expect(screen.getByText("Araç #10")).toBeInTheDocument(),
    );
    expect(
      screen.getByText(adminMaintenanceText.headers.vehicle),
    ).toBeInTheDocument();
    expect(
      screen.getByText(adminMaintenanceText.headers.maintenanceType),
    ).toBeInTheDocument();
    expect(
      screen.getByText(adminMaintenanceText.headers.status),
    ).toBeInTheDocument();
  });
});
