import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";
import { VehiclesModule } from "../VehiclesModule";
import {
  vehicleTableText,
  vehicleHeaderText,
} from "../../../resources/tr/vehicles";
import { Vehicle } from "../../../types";

// framer-motion passthrough
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
  },
}));

// Mock vehicle service
vi.mock("../../../api/vehicles", () => ({
  vehicleService: {
    getAll: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    exportExcel: vi.fn(),
    downloadTemplate: vi.fn(),
    uploadExcel: vi.fn(),
  },
}));

// Mock NotificationContext so useNotify works without the provider
vi.mock("../../../context/NotificationContext", () => ({
  useNotify: () => ({ notify: vi.fn() }),
}));

const MOCK_VEHICLES: Vehicle[] = [
  {
    id: 1,
    plaka: "34ABC123",
    marka: "Mercedes",
    model: "Actros",
    yil: 2022,
    hedef_tuketim: 32,
    aktif: true,
    yakit_tipi: "DIZEL",
  },
  {
    id: 2,
    plaka: "06XYZ789",
    marka: "Ford",
    model: "Cargo",
    yil: 2020,
    hedef_tuketim: 28,
    aktif: false,
    yakit_tipi: "DIZEL",
  },
];

describe("VehiclesModule", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const { vehicleService } = await import("../../../api/vehicles");
    (vehicleService.getAll as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: MOCK_VEHICLES,
      total: 2,
    });
  });

  it("renders the Add Vehicle button", async () => {
    render(<VehiclesModule />);
    // VehicleHeader renders the add button
    await waitFor(() => {
      expect(screen.getByText(vehicleHeaderText.addButton)).toBeInTheDocument();
    });
  });

  it("shows vehicle plates after data loads", async () => {
    render(<VehiclesModule />);
    await waitFor(() => {
      expect(screen.getByText("34ABC123")).toBeInTheDocument();
    });
    expect(screen.getByText("06XYZ789")).toBeInTheDocument();
  });

  it("shows fleet title heading", async () => {
    render(<VehiclesModule />);
    await waitFor(() => {
      expect(screen.getByText(vehicleTableText.title)).toBeInTheDocument();
    });
  });

  it("shows total count when vehicles are loaded", async () => {
    render(<VehiclesModule />);
    await waitFor(() => {
      expect(
        screen.getByText(vehicleTableText.totalCount(2)),
      ).toBeInTheDocument();
    });
  });

  it("shows empty state when service returns no vehicles", async () => {
    const { vehicleService } = await import("../../../api/vehicles");
    (vehicleService.getAll as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [],
      total: 0,
    });
    render(<VehiclesModule />);
    await waitFor(() => {
      expect(screen.getByText(vehicleTableText.emptyTitle)).toBeInTheDocument();
    });
  });

  it("does NOT render pagination when total fits on one page", async () => {
    render(<VehiclesModule />);
    // total=2, ITEMS_PER_PAGE=24 → 1 page → no pagination
    await waitFor(() => {
      expect(screen.queryByText(/Sayfa 1/)).not.toBeInTheDocument();
    });
  });
});
