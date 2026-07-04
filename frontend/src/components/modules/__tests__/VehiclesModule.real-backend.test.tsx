/**
 * 0-mock epiği: VehiclesModule.test.tsx'in mock'lu senaryolarına ek olarak,
 * gerçek backend'e karşı çalışan bir sürüm. Test DB paylaşımlı olabileceği
 * (paralel diğer ajanlar/testler) için sayım/liste doğrulamaları benzersiz
 * bir `marka` değeriyle (Date.now() suffix'li) arama filtresine
 * daraltılarak yapılıyor — böylece kalıntı veriler testi kırmaz.
 *
 * Orijinal mock'lu dosya (VehiclesModule.test.tsx) korunuyor: MOCK_VEHICLES
 * sabit veri kümesiyle davranışı belgeliyor ve hızlı/izole kalıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

// framer-motion passthrough (harmless third-party UI-lib mock)
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
  },
}));

// NotificationContext'in gerçek Provider'ı test-utils'teki AllTheProviders
// tarafından sarılmıyor (useNotify Provider dışında çağrılırsa throw eder).
// Bu backend'den bağımsız, saf bir test-altyapısı gereği — "harmless" mock.
const notifyMock = vi.fn();
vi.mock("../../../context/NotificationContext", async () => {
  const actual = await vi.importActual<any>(
    "../../../context/NotificationContext",
  );
  return {
    ...actual,
    useNotify: () => ({ notify: notifyMock }),
  };
});

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("VehiclesModule (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let VehiclesModule: typeof import("../VehiclesModule").VehiclesModule;
  let vehicleTableText: typeof import("../../../resources/tr/vehicles").vehicleTableText;
  let vehicleHeaderText: typeof import("../../../resources/tr/vehicles").vehicleHeaderText;
  let vehicleFilterText: typeof import("../../../resources/tr/vehicles").vehicleFilterText;
  let authToken: string;
  const suffix = Date.now();
  const marka = `ZmMarka${suffix}`;
  // Backend plaka regex: ^[0-9]{2}[\s-]?[A-ZÇĞİÖŞÜ]{1,5}[\s-]?[0-9]{2,4}$
  // → exactly 2-4 trailing digits, so use last 3 digits of the timestamp
  // plus a single distinguishing digit (4 digits total).
  // `validate_plaka_str` (app/core/entities/models.py) NORMALIZES the plaka
  // to "DD LL DDDD" (space-separated) regardless of input spacing — the UI
  // always renders the normalized form, so assertions must expect it too.
  const plakaAktif = `34 ZM ${suffix.toString().slice(-3)}1`;
  const plakaPasif = `34 ZM ${suffix.toString().slice(-3)}2`;
  let aktifVehicleId: number;
  let pasifVehicleId: number;

  async function createVehicle(plaka: string, aktif: boolean) {
    const resp = await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({
        plaka,
        marka,
        model: "TestModel",
        yil: 2022,
        hedef_tuketim: 30,
        aktif,
        yakit_tipi: "DIZEL",
      }),
    });
    const created = await resp.json();
    if (!resp.ok || !created.id) {
      throw new Error(
        `Vehicle creation failed (${resp.status}): ${JSON.stringify(created)}`,
      );
    }
    return created.id as number;
  }

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor, fireEvent } = await import(
      "../../../test/test-utils"
    ));
    ({ VehiclesModule } = await import("../VehiclesModule"));
    ({ vehicleTableText, vehicleHeaderText, vehicleFilterText } = await import(
      "../../../resources/tr/vehicles"
    ));

    aktifVehicleId = await createVehicle(plakaAktif, true);
    pasifVehicleId = await createVehicle(plakaPasif, false);
  }, 20000);

  afterAll(async () => {
    for (const id of [aktifVehicleId, pasifVehicleId]) {
      if (id) {
        await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/${id}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${authToken}` },
        }).catch(() => {});
      }
    }
    vi.unstubAllEnvs();
  });

  it("renders the Add Vehicle button", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<VehiclesModule />);
    await waitFor(
      () => {
        expect(
          screen.getByText(vehicleHeaderText.addButton),
        ).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  }, 15000);

  it("shows fleet title heading", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<VehiclesModule />);
    await waitFor(
      () => {
        expect(screen.getByText(vehicleTableText.title)).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  }, 15000);

  it("shows only the active vehicle plate when searching by unique marka (default aktif-only filter)", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<VehiclesModule />);
    await waitFor(
      () => {
        expect(
          screen.getByText(vehicleHeaderText.addButton),
        ).toBeInTheDocument();
      },
      { timeout: 10000 },
    );

    const searchInput = screen.getByPlaceholderText(
      vehicleFilterText.searchPlaceholder,
    );
    sessionStorage.setItem("access_token", authToken);
    fireEvent.change(searchInput, { target: { value: marka } });

    await waitFor(
      () => {
        expect(screen.getByText(plakaAktif)).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
    // default showOnlyActive=true → pasif vehicle should NOT show
    expect(screen.queryByText(plakaPasif)).not.toBeInTheDocument();
    expect(
      screen.getByText(vehicleTableText.totalCount(1)),
    ).toBeInTheDocument();
  }, 15000);

  it("shows both vehicles (active + inactive) when active-only filter is toggled off", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<VehiclesModule />);
    await waitFor(
      () => {
        expect(
          screen.getByText(vehicleHeaderText.addButton),
        ).toBeInTheDocument();
      },
      { timeout: 10000 },
    );

    const searchInput = screen.getByPlaceholderText(
      vehicleFilterText.searchPlaceholder,
    );
    sessionStorage.setItem("access_token", authToken);
    fireEvent.change(searchInput, { target: { value: marka } });

    await waitFor(
      () => {
        expect(screen.getByText(plakaAktif)).toBeInTheDocument();
      },
      { timeout: 10000 },
    );

    // toggle "Aktif Araçlar" off to include the inactive vehicle
    sessionStorage.setItem("access_token", authToken);
    fireEvent.click(screen.getByText(vehicleFilterText.activeOnly));

    await waitFor(
      () => {
        expect(screen.getByText(plakaPasif)).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
    expect(screen.getByText(plakaAktif)).toBeInTheDocument();
    expect(
      screen.getByText(vehicleTableText.totalCount(2)),
    ).toBeInTheDocument();
  }, 15000);

  it("shows empty state when a search matches no vehicles", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<VehiclesModule />);
    await waitFor(
      () => {
        expect(
          screen.getByText(vehicleHeaderText.addButton),
        ).toBeInTheDocument();
      },
      { timeout: 10000 },
    );

    const searchInput = screen.getByPlaceholderText(
      vehicleFilterText.searchPlaceholder,
    );
    sessionStorage.setItem("access_token", authToken);
    fireEvent.change(searchInput, {
      target: { value: `nonexistent-marka-${suffix}-zzz` },
    });

    await waitFor(
      () => {
        expect(
          screen.getByText(vehicleTableText.emptyTitle),
        ).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  }, 15000);
});
