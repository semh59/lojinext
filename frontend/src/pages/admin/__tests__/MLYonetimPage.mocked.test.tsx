import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import AdminModelManagementPage from "../MLYonetimPage";
import { adminMlText } from "../../../resources/tr/admin";

// Scenarios kept mocked because they require fields the real backend's
// EgitimKuyrugu/MLTaskRead model does not have columns for at all today
// (metrics, training_time_seconds, error_message, trigger_reason) — see
// MLYonetimPage.test.tsx for the real-backend coverage of this page
// (queue/badge/date rendering against the actual contract).

vi.mock("../../../api/admin", () => ({
  adminMlApi: {
    getQueue: vi.fn(),
    triggerTraining: vi.fn(),
  },
}));

vi.mock("../../../api/vehicles", () => ({
  vehicleService: {
    getAll: vi.fn(),
  },
}));

vi.mock("../../../context/NotificationContext", () => ({
  useNotify: () => ({ notify: vi.fn() }),
  NotificationProvider: ({ children }: any) => <>{children}</>,
}));

vi.mock("../../../hooks/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

const MOCK_QUEUE = [
  {
    id: 1,
    arac_id: 10,
    durum: "completed",
    metrics: { algorithm: "lightgbm", rmse: 3.42 },
    training_time_seconds: 12.5,
    error_message: null,
    trigger_reason: "manual",
    created_at: "2026-06-01T10:00:00Z",
  },
  {
    id: 2,
    arac_id: 11,
    durum: "running",
    metrics: null,
    training_time_seconds: null,
    error_message: null,
    trigger_reason: "scheduled",
    created_at: "2026-06-02T08:00:00Z",
  },
  {
    id: 3,
    arac_id: 12,
    durum: "failed",
    metrics: null,
    training_time_seconds: null,
    error_message: "Out of memory",
    trigger_reason: null,
    created_at: "2026-06-02T09:00:00Z",
  },
];

const MOCK_VEHICLES = {
  items: [
    { id: 10, plaka: "34ABC001", marka: "Mercedes", model: "Actros" },
    { id: 11, plaka: "06DEF002", marka: "Volvo", model: "FH" },
  ],
  total: 2,
  skip: 0,
  limit: 100,
};

describe("AdminModelManagementPage (mocked scenarios)", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const { adminMlApi } = await import("../../../api/admin");
    const { vehicleService } = await import("../../../api/vehicles");
    (adminMlApi.getQueue as ReturnType<typeof vi.fn>).mockResolvedValue(
      MOCK_QUEUE,
    );
    (vehicleService.getAll as ReturnType<typeof vi.fn>).mockResolvedValue(
      MOCK_VEHICLES,
    );
  });

  it("renders stat cards: total/running tasks count", async () => {
    render(<AdminModelManagementPage />);
    await waitFor(() => {
      expect(screen.getByText("3")).toBeInTheDocument(); // totalTasks
      expect(screen.getByText("1")).toBeInTheDocument(); // runningCount
    });
  });

  it("shows algorithm/rmse for completed task", async () => {
    render(<AdminModelManagementPage />);
    await waitFor(() => {
      const cell = document.body.querySelector("td span.text-xs.font-medium");
      expect(cell?.textContent).toMatch(/lightgbm/);
    });
  });

  it("shows training duration in seconds", async () => {
    render(<AdminModelManagementPage />);
    await waitFor(() => {
      expect(screen.getByText(/12\.5\s*sn/)).toBeInTheDocument();
    });
  });

  it("shows error message for failed task", async () => {
    render(<AdminModelManagementPage />);
    await waitFor(() => {
      expect(screen.getByText("Out of memory")).toBeInTheDocument();
    });
  });

  it("latest rmse shown in card", async () => {
    render(<AdminModelManagementPage />);
    await waitFor(() => {
      const rmseText = screen.getAllByText("3.42");
      expect(rmseText.length).toBeGreaterThan(0);
    });
  });

  it("shows empty state when queue is empty", async () => {
    const { adminMlApi } = await import("../../../api/admin");
    (adminMlApi.getQueue as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    render(<AdminModelManagementPage />);
    await waitFor(() => {
      expect(screen.getByText(adminMlText.table.empty)).toBeInTheDocument();
    });
  });

  it("shows 'Araç bulunamadı' when no vehicles", async () => {
    const { vehicleService } = await import("../../../api/vehicles");
    (vehicleService.getAll as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [],
      total: 0,
    });
    render(<AdminModelManagementPage />);
    await waitFor(() => {
      expect(screen.getByText(adminMlText.vehicleNotFound)).toBeInTheDocument();
    });
  });

  it("calls triggerTraining on button click with selected vehicle", async () => {
    const { adminMlApi } = await import("../../../api/admin");
    (adminMlApi.triggerTraining as ReturnType<typeof vi.fn>).mockResolvedValue({
      status: "queued",
    });
    render(<AdminModelManagementPage />);
    await waitFor(() => screen.getByText(/34ABC001/));
    // Auto-select effect'ine (sayfa ilk aracı kendisi seçiyor) GÜVENME:
    // CI yükünde click, effect'in state commit'inden önce gelebiliyor ve
    // handler selectedVehicleId=null görüp no-op yapıyordu (run 28873564005,
    // spy 0 çağrı). Açık seçim testi deterministik yapar.
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "10" } });
    const btn = screen.getByText(adminMlText.startTraining);
    fireEvent.click(btn);
    await waitFor(() => {
      expect(adminMlApi.triggerTraining).toHaveBeenCalledWith(10);
    });
  });
});
