/**
 * 0-mock epiği: TripsModule.test.tsx'in mock'lu senaryolarına ek olarak,
 * gerçek backend'e karşı çalışan bir sürüm. `tripService`, `services/api`
 * (vehiclesApi/driversApi/locationService/weatherApi), `dorseService` ve
 * `preferences` artık GERÇEK HTTP çağrıları yapıyor — hiçbiri mock'lanmıyor.
 * Sadece zararsız UI-lib mock'ları (Modal basitleştirme, framer-motion,
 * sonner, RequirePermission passthrough, react-virtual) korunuyor — bunlar
 * backend çağrısı değil, saf render/animasyon kısayolları.
 *
 * `tripService.getAll`'ın path'i orval-üretimi client kullanıyor (path zaten
 * "/api/v1/..." prefix'ini içeriyor) → REAL_BACKEND_ORIGIN (origin only).
 *
 * Orijinal mock'lu dosya (TripsModule.test.tsx) korunuyor: "shows error panel
 * when list request fails" senaryosu (500 hata enjeksiyonu) gerçek backend'e
 * karşı pratik olarak tetiklenemez.
 */
import { beforeAll, afterAll, describe, expect, it, vi } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

vi.mock("../../../components/ui/Modal", () => ({
  Modal: ({ children, isOpen, title }: any) =>
    isOpen ? (
      <div role="dialog" aria-label={title || "modal"}>
        <h2>{title}</h2>
        {children}
      </div>
    ) : null,
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    loading: vi.fn(),
  },
}));

vi.mock("framer-motion", () => ({
  motion: new Proxy(
    {},
    {
      get: (_target, key: string) => {
        const tag =
          key === "tr"
            ? "tr"
            : key === "span"
              ? "span"
              : key === "p"
                ? "p"
                : "div";
        return ({ children, ...props }: any) => {
          const Tag = tag as keyof JSX.IntrinsicElements;
          return <Tag {...props}>{children}</Tag>;
        };
      },
    },
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

vi.mock("../../../components/auth/RequirePermission", () => ({
  RequirePermission: ({ children }: any) => <>{children}</>,
}));

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: (args: any) => {
    const count = args?.count ?? 0;
    return {
      getTotalSize: () => count * 140,
      getVirtualItems: () =>
        Array.from({ length: count }).map((_, index) => ({
          key: `row-${index}`,
          index,
          size: 140,
          start: index * 140,
        })),
    };
  },
}));

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("TripsModule (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let TripsModule: typeof import("../TripsModule").TripsModule;
  let useTripStore: typeof import("../../../stores/use-trip-store").useTripStore;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor, fireEvent } = await import(
      "../../../test/test-utils"
    ));
    ({ TripsModule } = await import("../TripsModule"));
    ({ useTripStore } = await import("../../../stores/use-trip-store"));
  }, 20000);

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("renders core header actions against the real backend", async () => {
    sessionStorage.setItem("access_token", authToken);
    localStorage.clear();
    useTripStore.persist.clearStorage();
    useTripStore.getState().reset();
    await useTripStore.persist.rehydrate();

    render(<TripsModule />);

    expect(
      await screen.findByRole(
        "heading",
        { level: 1, name: /sefer yönetimi/i },
        { timeout: 10000 },
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/yakıt performansı/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /yeni sefer oluştur/i }),
    ).toBeInTheDocument();
  }, 15000);

  it("opens the create-trip modal (real vehicles/drivers/locations/trailers fetch)", async () => {
    sessionStorage.setItem("access_token", authToken);
    localStorage.clear();
    useTripStore.persist.clearStorage();
    useTripStore.getState().reset();
    await useTripStore.persist.rehydrate();

    render(<TripsModule />);

    const createButton = await screen.findByRole(
      "button",
      { name: /yeni sefer oluştur/i },
      { timeout: 10000 },
    );
    fireEvent.click(createButton);

    await waitFor(
      () => {
        expect(useTripStore.getState().isFormOpen).toBe(true);
      },
      { timeout: 10000 },
    );
    // Modal (mocked to a plain dialog) renders without crashing even
    // though TripFormModal's own vehicle/driver/location/trailer queries
    // now hit the real backend.
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  }, 15000);

  it("opens the fuel performance panel with real analytics data", async () => {
    sessionStorage.setItem("access_token", authToken);
    localStorage.clear();
    useTripStore.persist.clearStorage();
    useTripStore.getState().reset();
    await useTripStore.persist.rehydrate();

    render(<TripsModule />);

    const toggle = await screen.findByText(
      /yakıt performansı/i,
      {},
      { timeout: 10000 },
    );
    fireEvent.click(toggle);

    expect(
      await screen.findByText(/paneli kapat/i, {}, { timeout: 10000 }),
    ).toBeInTheDocument();
  }, 15000);
});
