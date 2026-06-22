import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import AdminModelManagementPage from "../MLYonetimPage";
import { adminMlText } from "../../../resources/tr/admin";

// Mock admin-service
vi.mock("../../../api/admin", () => ({
  adminMlApi: {
    getQueue: vi.fn(),
    triggerTraining: vi.fn(),
  },
}));

// Mock vehicle-service
vi.mock("../../../api/vehicles", () => ({
  vehicleService: {
    getAll: vi.fn(),
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

describe("AdminModelManagementPage (MLYonetimPage)", () => {
  let notifyMock: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    vi.clearAllMocks();
    notifyMock = vi.fn();
    const { adminMlApi } = await import("../../../api/admin");
    const { vehicleService } = await import("../../../api/vehicles");
    (adminMlApi.getQueue as ReturnType<typeof vi.fn>).mockResolvedValue(
      MOCK_QUEUE,
    );
    (vehicleService.getAll as ReturnType<typeof vi.fn>).mockResolvedValue(
      MOCK_VEHICLES,
    );

    // Re-mock useNotify with fresh mock per test
    const notifMod = await import("../../../context/NotificationContext");
    (notifMod.useNotify as unknown as ReturnType<typeof vi.fn>) = vi
      .fn()
      .mockReturnValue({ notify: notifyMock });
  });

  it("renders page heading", async () => {
    render(<AdminModelManagementPage />);
    expect(screen.getByText(adminMlText.heading)).toBeInTheDocument();
  });

  it("renders page description", async () => {
    render(<AdminModelManagementPage />);
    expect(screen.getByText(adminMlText.description)).toBeInTheDocument();
  });

  it("renders start training button", async () => {
    render(<AdminModelManagementPage />);
    expect(screen.getByText(adminMlText.startTraining)).toBeInTheDocument();
  });

  it("shows vehicle options in selector after loading", async () => {
    render(<AdminModelManagementPage />);
    await waitFor(() => {
      expect(screen.getByText(/34ABC001/)).toBeInTheDocument();
    });
  });

  it("renders stat cards: total tasks", async () => {
    render(<AdminModelManagementPage />);
    expect(screen.getByText(adminMlText.cards.totalTasks)).toBeInTheDocument();
    // totalTasks count = 3
    await waitFor(() => {
      expect(screen.getByText("3")).toBeInTheDocument();
    });
  });

  it("renders stat card: running tasks count", async () => {
    render(<AdminModelManagementPage />);
    expect(
      screen.getByText(adminMlText.cards.runningTasks),
    ).toBeInTheDocument();
    // runningCount = 1
    await waitFor(() => {
      expect(screen.getByText("1")).toBeInTheDocument();
    });
  });

  it("renders training queue table title", async () => {
    render(<AdminModelManagementPage />);
    expect(screen.getByText(adminMlText.table.title)).toBeInTheDocument();
  });

  it("shows queue rows with vehicle prefix after loading", async () => {
    render(<AdminModelManagementPage />);
    await waitFor(() => {
      expect(screen.getByText("Araç #10")).toBeInTheDocument();
      expect(screen.getByText("Araç #11")).toBeInTheDocument();
      expect(screen.getByText("Araç #12")).toBeInTheDocument();
    });
  });

  it("shows task statuses as badges", async () => {
    render(<AdminModelManagementPage />);
    await waitFor(() => {
      expect(screen.getByText("completed")).toBeInTheDocument();
      expect(screen.getByText("running")).toBeInTheDocument();
      expect(screen.getByText("failed")).toBeInTheDocument();
    });
  });

  it("shows algorithm/rmse for completed task", async () => {
    render(<AdminModelManagementPage />);
    await waitFor(() => {
      // component renders e.g. "lightgbm / 3.42" inside a span
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

  it("latest rmse shown in card", async () => {
    render(<AdminModelManagementPage />);
    await waitFor(() => {
      // latestRmse = 3.42 → "3.42"
      const rmseText = screen.getAllByText("3.42");
      expect(rmseText.length).toBeGreaterThan(0);
    });
  });

  it("calls triggerTraining on button click with selected vehicle", async () => {
    const { adminMlApi } = await import("../../../api/admin");
    (adminMlApi.triggerTraining as ReturnType<typeof vi.fn>).mockResolvedValue({
      status: "queued",
    });
    render(<AdminModelManagementPage />);
    await waitFor(() => screen.getByText(/34ABC001/));
    const btn = screen.getByText(adminMlText.startTraining);
    fireEvent.click(btn);
    await waitFor(() => {
      expect(adminMlApi.triggerTraining).toHaveBeenCalledWith(10);
    });
  });
});
