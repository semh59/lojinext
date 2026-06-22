import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "../../test/test-utils";
import FuelPage from "../FuelPage";

// Servisleri mock'la
vi.mock("../../api/fuel", () => ({
  fuelService: {
    getAll: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    getStats: vi.fn().mockResolvedValue({ toplam_litre: 0, toplam_tutar: 0 }),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    exportExcel: vi.fn(),
  },
}));

vi.mock("../../api/predictions", () => ({
  predictionService: {
    getComparison: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock("../../api/vehicles", () => ({
  vehicleService: {
    getAll: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
}));

vi.mock("../../context/NotificationContext", () => ({
  useNotify: () => ({ notify: vi.fn() }),
  NotificationProvider: ({ children }: any) => <>{children}</>,
}));

vi.mock("../../hooks/use-url-state", () => ({
  useUrlState: (initial: any) => [initial, vi.fn()],
}));

// Alt bileşenleri stub'la — davranış değil yapı testi
vi.mock("../../components/fuel/FuelTable", () => ({
  FuelTable: () => <div data-testid="fuel-table">Yakıt Tablosu</div>,
}));
vi.mock("../../components/fuel/FuelModal", () => ({
  FuelModal: ({ isOpen }: { isOpen: boolean }) =>
    isOpen ? <div role="dialog">Yakıt Modal</div> : null,
}));
vi.mock("../../components/fuel/FuelStats", () => ({
  FuelStats: () => <div data-testid="fuel-stats">İstatistikler</div>,
}));
vi.mock("../../components/fuel/FuelHeader", () => ({
  FuelHeader: ({ onAdd }: { onAdd: () => void }) => (
    <button onClick={onAdd} data-testid="add-fuel-btn">
      Yakıt Ekle
    </button>
  ),
}));
vi.mock("../../components/fuel/FuelFilters", () => ({
  FuelFilters: () => <div data-testid="fuel-filters">Filtreler</div>,
}));
vi.mock("../../components/fuel/ComparisonWidget", () => ({
  ComparisonWidget: () => null,
}));
vi.mock("../../components/fuel/FuelPagination", () => ({
  FuelPagination: () => null,
}));
vi.mock("../../components/common/ErrorBoundary", () => ({
  default: ({ children }: any) => <>{children}</>,
}));

describe("FuelPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("temel bileşenler render edilir", async () => {
    render(<FuelPage />);
    await waitFor(() => {
      expect(screen.getByTestId("fuel-table")).toBeInTheDocument();
      expect(screen.getByTestId("fuel-stats")).toBeInTheDocument();
      expect(screen.getByTestId("fuel-filters")).toBeInTheDocument();
    });
  });

  it("yakıt ekle butonu modal açar", async () => {
    render(<FuelPage />);
    await waitFor(() =>
      expect(screen.getByTestId("add-fuel-btn")).toBeInTheDocument(),
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    screen.getByTestId("add-fuel-btn").click();
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
  });
});
