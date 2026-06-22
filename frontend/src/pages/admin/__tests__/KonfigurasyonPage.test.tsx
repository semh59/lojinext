import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import AdminConfigurationPage from "../KonfigurasyonPage";
import { adminConfigurationText } from "../../../resources/tr/admin";

// Mock admin-service
vi.mock("../../../api/admin", () => ({
  adminApi: {
    getConfigs: vi.fn(),
    updateConfig: vi.fn(),
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

const MOCK_CONFIGS = [
  {
    anahtar: "ANOMALY_Z_THRESHOLD",
    deger: 2.5,
    tip: "float",
    birim: "σ",
    min_deger: 1.0,
    max_deger: 5.0,
    grup: "ML",
    aciklama: "Anomali tespiti için Z-skoru eşiği",
    yeniden_baslat: false,
  },
  {
    anahtar: "VEHICLE_AGE_DEGRADATION_RATE",
    deger: 0.01,
    tip: "float",
    birim: undefined,
    grup: "ML",
    aciklama: "Yıllık araç yaşı bozulma oranı",
    yeniden_baslat: true,
  },
  {
    anahtar: "LOG_LEVEL",
    deger: "INFO",
    tip: "string",
    birim: undefined,
    grup: "CORE",
    aciklama: "Uygulama log seviyesi",
    yeniden_baslat: false,
  },
];

describe("AdminConfigurationPage (KonfigurasyonPage)", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const { adminApi } = await import("../../../api/admin");
    (adminApi.getConfigs as ReturnType<typeof vi.fn>).mockResolvedValue(
      MOCK_CONFIGS,
    );
  });

  it("renders page heading after data loads", async () => {
    render(<AdminConfigurationPage />);
    await waitFor(() =>
      expect(
        screen.getByText(adminConfigurationText.heading),
      ).toBeInTheDocument(),
    );
  });

  it("renders page description after data loads", async () => {
    render(<AdminConfigurationPage />);
    await waitFor(() =>
      expect(
        screen.getByText(adminConfigurationText.description),
      ).toBeInTheDocument(),
    );
  });

  it("shows loading text while fetching", async () => {
    const { adminApi } = await import("../../../api/admin");
    (adminApi.getConfigs as ReturnType<typeof vi.fn>).mockReturnValue(
      new Promise(() => {}),
    );
    render(<AdminConfigurationPage />);
    expect(
      screen.getByText(adminConfigurationText.loading),
    ).toBeInTheDocument();
  });

  it("renders config keys after loading", async () => {
    render(<AdminConfigurationPage />);
    await waitFor(() => {
      expect(screen.getByText("ANOMALY_Z_THRESHOLD")).toBeInTheDocument();
      expect(
        screen.getByText("VEHICLE_AGE_DEGRADATION_RATE"),
      ).toBeInTheDocument();
      expect(screen.getByText("LOG_LEVEL")).toBeInTheDocument();
    });
  });

  it("shows config descriptions", async () => {
    render(<AdminConfigurationPage />);
    await waitFor(() => {
      expect(
        screen.getByText("Anomali tespiti için Z-skoru eşiği"),
      ).toBeInTheDocument();
    });
  });

  it("shows group section headers with suffix", async () => {
    render(<AdminConfigurationPage />);
    await waitFor(() => {
      // Groups: ML and CORE; heading is "{group} ayarları"
      expect(screen.getAllByText(/ayarları/i).length).toBeGreaterThan(0);
    });
  });

  it("renders 'yeniden baslat' badge for configs that need restart", async () => {
    render(<AdminConfigurationPage />);
    await waitFor(() => {
      const reloadBadges = screen.getAllByText(
        adminConfigurationText.reloadRequired,
      );
      expect(reloadBadges.length).toBeGreaterThan(0);
    });
  });

  it("renders save buttons for each config", async () => {
    render(<AdminConfigurationPage />);
    await waitFor(() =>
      expect(screen.getByText("ANOMALY_Z_THRESHOLD")).toBeInTheDocument(),
    );
    const saveBtns = screen.getAllByText(adminConfigurationText.actions.save);
    expect(saveBtns.length).toBeGreaterThanOrEqual(3);
  });

  it("shows birim (unit) label when present", async () => {
    render(<AdminConfigurationPage />);
    await waitFor(() => {
      expect(screen.getByText("σ")).toBeInTheDocument();
    });
  });

  it("save button is disabled when value unchanged", async () => {
    render(<AdminConfigurationPage />);
    // Wait for both: data visible AND localValues useEffect to populate
    // (useEffect runs after the render that shows the data)
    await waitFor(() => {
      expect(screen.getByText("ANOMALY_Z_THRESHOLD")).toBeInTheDocument();
      const saveBtns = screen.getAllByRole("button", {
        name: adminConfigurationText.actions.save,
      });
      expect(saveBtns[0]).toBeDisabled();
    });
  });

  it("save button becomes enabled when value is changed", async () => {
    render(<AdminConfigurationPage />);
    await waitFor(() =>
      expect(screen.getByText("ANOMALY_Z_THRESHOLD")).toBeInTheDocument(),
    );
    const inputs = screen.getAllByPlaceholderText(
      adminConfigurationText.valuePlaceholder,
    );
    // Change first input
    fireEvent.change(inputs[0], { target: { value: "3.0" } });
    const saveBtns = screen.getAllByRole("button", {
      name: adminConfigurationText.actions.save,
    });
    await waitFor(() => {
      expect(saveBtns[0]).not.toBeDisabled();
    });
  });

  it("calls updateConfig when save button clicked after change", async () => {
    const { adminApi } = await import("../../../api/admin");
    (adminApi.updateConfig as ReturnType<typeof vi.fn>).mockResolvedValue({});
    render(<AdminConfigurationPage />);
    await waitFor(() =>
      expect(screen.getByText("ANOMALY_Z_THRESHOLD")).toBeInTheDocument(),
    );
    const inputs = screen.getAllByPlaceholderText(
      adminConfigurationText.valuePlaceholder,
    );
    fireEvent.change(inputs[0], { target: { value: "3.0" } });
    const saveBtns = screen.getAllByRole("button", {
      name: adminConfigurationText.actions.save,
    });
    await waitFor(() => expect(saveBtns[0]).not.toBeDisabled());
    fireEvent.click(saveBtns[0]);
    await waitFor(() => {
      expect(adminApi.updateConfig).toHaveBeenCalledWith(
        "ANOMALY_Z_THRESHOLD",
        3.0,
        "Updated from admin panel",
      );
    });
  });
});
