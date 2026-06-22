import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import AdminNotificationsPage from "../BildirimlerPage";
import { adminNotificationsText } from "../../../resources/tr/admin";

// Mock admin-service
vi.mock("../../../api/admin", () => ({
  adminNotificationsApi: {
    getRules: vi.fn(),
    createRule: vi.fn(),
  },
  adminRolesApi: {
    getAll: vi.fn().mockResolvedValue([
      { id: 1, ad: "admin", yetkiler: {} },
      { id: 2, ad: "operator", yetkiler: {} },
    ]),
  },
}));

// Mock usePageTitle
vi.mock("../../../hooks/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

// Mock Modal
vi.mock("../../../components/ui/Modal", () => ({
  Modal: ({ isOpen, children, title }: any) =>
    isOpen ? (
      <div role="dialog" aria-label={title}>
        <h2>{title}</h2>
        {children}
      </div>
    ) : null,
}));

// Mock sonner
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const MOCK_RULES = [
  {
    id: 1,
    olay_tipi: "FUEL_ANOMALY",
    kanallar: ["EMAIL", "PUSH"],
    alici_rol_id: 1,
    sablon_icerik: "Yakıt anomalisi tespit edildi",
    aktif: true,
  },
  {
    id: 2,
    olay_tipi: "TRIP_DELAY",
    kanallar: ["SMS"],
    alici_rol_id: 2,
    sablon_icerik: null,
    aktif: false,
  },
];

describe("AdminNotificationsPage (BildirimlerPage)", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const { adminNotificationsApi } = await import("../../../api/admin");
    (
      adminNotificationsApi.getRules as ReturnType<typeof vi.fn>
    ).mockResolvedValue(MOCK_RULES);
  });

  it("renders page heading", async () => {
    render(<AdminNotificationsPage />);
    expect(
      screen.getByText(adminNotificationsText.heading),
    ).toBeInTheDocument();
  });

  it("renders page description", async () => {
    render(<AdminNotificationsPage />);
    expect(
      screen.getByText(adminNotificationsText.description),
    ).toBeInTheDocument();
  });

  it("renders add rule button", async () => {
    render(<AdminNotificationsPage />);
    expect(
      screen.getByText(adminNotificationsText.addRule),
    ).toBeInTheDocument();
  });

  it("renders section title with bell icon area", async () => {
    render(<AdminNotificationsPage />);
    expect(
      screen.getByText(adminNotificationsText.sectionTitle),
    ).toBeInTheDocument();
  });

  it("shows notification rules after loading", async () => {
    render(<AdminNotificationsPage />);
    await waitFor(() => {
      expect(screen.getByText("FUEL_ANOMALY")).toBeInTheDocument();
      expect(screen.getByText("TRIP_DELAY")).toBeInTheDocument();
    });
  });

  it("shows channel badges for rules", async () => {
    render(<AdminNotificationsPage />);
    await waitFor(() => {
      expect(screen.getByText("EMAIL")).toBeInTheDocument();
      expect(screen.getByText("PUSH")).toBeInTheDocument();
      expect(screen.getByText("SMS")).toBeInTheDocument();
    });
  });

  it("shows active/passive status badges", async () => {
    render(<AdminNotificationsPage />);
    await waitFor(() => {
      expect(
        screen.getByText(adminNotificationsText.statuses.active),
      ).toBeInTheDocument();
      expect(
        screen.getByText(adminNotificationsText.statuses.passive),
      ).toBeInTheDocument();
    });
  });

  it("shows role prefix for rules", async () => {
    render(<AdminNotificationsPage />);
    await waitFor(() => {
      // rolePrefix "Rol" + " #1" and "#2"
      expect(screen.getByText("Rol #1")).toBeInTheDocument();
    });
  });

  it("shows template content when present", async () => {
    render(<AdminNotificationsPage />);
    await waitFor(() => {
      expect(
        screen.getByText("Yakıt anomalisi tespit edildi"),
      ).toBeInTheDocument();
    });
  });

  it("shows dash for missing template", async () => {
    render(<AdminNotificationsPage />);
    await waitFor(() => {
      const cells = screen.getAllByText("-");
      expect(cells.length).toBeGreaterThan(0);
    });
  });

  it("shows empty state when no rules", async () => {
    const { adminNotificationsApi } = await import("../../../api/admin");
    (
      adminNotificationsApi.getRules as ReturnType<typeof vi.fn>
    ).mockResolvedValue([]);
    render(<AdminNotificationsPage />);
    await waitFor(() => {
      expect(
        screen.getByText(adminNotificationsText.empty),
      ).toBeInTheDocument();
    });
  });

  it("opens modal when add rule button clicked", async () => {
    render(<AdminNotificationsPage />);
    const addBtn = screen.getByText(adminNotificationsText.addRule);
    fireEvent.click(addBtn);
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByText("Yeni Bildirim Kuralı")).toBeInTheDocument();
    });
  });

  it("modal contains olay tipi input", async () => {
    render(<AdminNotificationsPage />);
    fireEvent.click(screen.getByText(adminNotificationsText.addRule));
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    expect(screen.getByPlaceholderText(/FUEL_ANOMALY/)).toBeInTheDocument();
  });

  it("modal contains channel toggle buttons", async () => {
    render(<AdminNotificationsPage />);
    fireEvent.click(screen.getByText(adminNotificationsText.addRule));
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    // CHANNELS are EMAIL, PUSH, TELEGRAM, SMS — they appear inside the modal
    expect(
      screen.getAllByRole("button", { name: "EMAIL" }).length,
    ).toBeGreaterThan(0);
  });

  it("shows form validation error when submitting with no olay_tipi", async () => {
    render(<AdminNotificationsPage />);
    fireEvent.click(screen.getByText(adminNotificationsText.addRule));
    await waitFor(() => screen.getByRole("dialog"));
    // Submit without filling in form
    const submitBtn = screen.getByRole("button", { name: "Oluştur" });
    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText("Olay tipi zorunludur")).toBeInTheDocument();
    });
  });

  it("renders table headers", async () => {
    render(<AdminNotificationsPage />);
    await waitFor(() =>
      expect(screen.getByText("FUEL_ANOMALY")).toBeInTheDocument(),
    );
    expect(
      screen.getByText(adminNotificationsText.headers.eventType),
    ).toBeInTheDocument();
    expect(
      screen.getByText(adminNotificationsText.headers.channels),
    ).toBeInTheDocument();
    expect(
      screen.getByText(adminNotificationsText.headers.status),
    ).toBeInTheDocument();
  });
});
