/**
 * 0-mock epiği Faz 2: `useRouteSimulation` (mutation hook) DOKÜMANTE mock'lu
 * kalıyor — bu test sayfanın 3 ayrı render durumunu (idle/502-hata/başarı)
 * doğrudan hook state'i enjekte ederek doğruluyor; gerçek servis
 * davranışı zaten `services/api/__tests__/route-sim-service.test.ts`'te
 * gerçek backend'e karşı kanıtlandı (gerçek 200 başarı + gerçek 422 hata).
 * Burada gerçek bir 502'yi UI'dan tetiklemek E2E'nin işi (Playwright zaten
 * kapsıyor) — aynı domain, dilim4/5'teki "endpoint'in kendi
 * hata-eşleme/render mantığı testi" istisnasıyla aynı gerekçe.
 * `useLocations` gerçek backend'e çevrildi (ucuz, güvenli, tutarlılık için).
 * `recharts` mock'u UI kütüphanesi render'ı, dış sınır değil — dokümante.
 */
import {
  describe,
  expect,
  it,
  vi,
  beforeAll,
  beforeEach,
  afterAll,
} from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../test/real-backend";

const simState = vi.hoisted(() => ({
  current: {
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null as unknown,
    data: null as unknown,
  },
}));

vi.mock("../../hooks/useRouteSimulation", () => ({
  useRouteSimulation: () => simState.current,
}));

vi.mock("recharts", () => ({
  ComposedChart: ({ children }: any) => <div>{children}</div>,
  Line: () => null,
  Area: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
}));

const okData = {
  simulation_id: 1,
  created_at: "2026-06-14T00:00:00Z",
  summary: {
    distance_km: 150,
    duration_min: 120,
    total_l: 48,
    avg_l_per_100km: 32,
    total_ascent_m: 300,
    total_descent_m: 280,
  },
  segments: [
    {
      seq: 0,
      length_km: 0.5,
      grade_pct: 1,
      road_class: "motorway",
      sim_speed_kmh: 80,
      sim_l_per_100km: 30,
      sim_l_total: 0.15,
      eta_sec: 20,
      mid_lon: 29,
      mid_lat: 41,
      maxspeed_kmh: 90,
      traffic_speed_kmh: 80,
      congestion: "low",
      speed_source: "traffic",
    },
  ],
  raw_segment_count: 10,
  resampled_segment_count: 5,
  elevation_coverage_pct: 100,
  meta: {},
};

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("RouteLabPage (real backend)", () => {
  let render: typeof import("../../test/test-utils").render;
  let screen: typeof import("../../test/test-utils").screen;
  let RouteLabPage: typeof import("../RouteLabPage").default;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ render, screen } = await import("../../test/test-utils"));
    ({ default: RouteLabPage } = await import("../RouteLabPage"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  beforeEach(() => {
    simState.current = {
      mutate: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
      data: null,
    };
  });

  it("shows empty state initially", () => {
    render(<RouteLabPage />);
    expect(screen.getByRole("button", { name: /Simüle Et/i })).toBeTruthy();
    expect(screen.getByText(/güzergah seçip/i)).toBeTruthy();
  });

  it("shows mapped error message on 502", () => {
    simState.current.isError = true;
    simState.current.error = { response: { status: 502 } };
    render(<RouteLabPage />);
    expect(screen.getByText(/Mapbox.*erişilemez/i)).toBeTruthy();
  });

  it("renders summary + charts on success", () => {
    simState.current.data = okData;
    render(<RouteLabPage />);
    expect(screen.getByText("150.0 km")).toBeTruthy();
    expect(screen.getByText(/Segment profili/i)).toBeTruthy();
    expect(screen.getByText(/Tüketim haritası/i)).toBeTruthy();
  });
});
