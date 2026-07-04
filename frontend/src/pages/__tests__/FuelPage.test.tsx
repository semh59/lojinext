/**
 * 0-mock epiği: FuelPage'in kendi API çağrıları (fuel/vehicles/predictions/
 * reports servisleri) artık gerçek backend'e karşı çalışıyor — `vi.mock`
 * kaldırıldı. Alt bileşenler (`FuelTable`, `FuelModal`, vb.) hâlâ stub'lı
 * kalıyor çünkü orijinal test zaten "yapı testi, davranış testi değil"
 * niyetiyle yazılmış (bkz. yorum) — bunlar dış sınır değil, iç render
 * detayı; gerçek network round-trip'i sayfa seviyesindeki `useQuery`
 * çağrılarında gerçekleşiyor.
 */
import {
  beforeAll,
  afterAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../test/real-backend";

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

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("FuelPage (real backend)", () => {
  let render: typeof import("../../test/test-utils").render;
  let screen: typeof import("../../test/test-utils").screen;
  let waitFor: typeof import("../../test/test-utils").waitFor;
  let FuelPage: typeof import("../FuelPage").default;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ render, screen, waitFor } = await import("../../test/test-utils"));
    ({ default: FuelPage } = await import("../FuelPage"));
  }, 20000);

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  beforeEach(async () => {
    sessionStorage.setItem("access_token", await loginAsAdmin());
  });

  it("temel bileşenler render edilir", async () => {
    render(<FuelPage />);
    await waitFor(
      () => {
        expect(screen.getByTestId("fuel-table")).toBeInTheDocument();
        expect(screen.getByTestId("fuel-stats")).toBeInTheDocument();
        expect(screen.getByTestId("fuel-filters")).toBeInTheDocument();
      },
      { timeout: 15000 },
    );
  }, 20000);

  it("yakıt ekle butonu modal açar", async () => {
    render(<FuelPage />);
    await waitFor(
      () => expect(screen.getByTestId("add-fuel-btn")).toBeInTheDocument(),
      { timeout: 15000 },
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    screen.getByTestId("add-fuel-btn").click();
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
  }, 20000);
});
