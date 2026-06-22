import { describe, expect, it, vi, beforeEach } from "vitest";

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

vi.mock("../../hooks/use-locations", () => ({
  useLocations: () => ({
    useGetLocations: () => ({ data: [] }),
  }),
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

import { render, screen } from "../../test/test-utils";
import RouteLabPage from "../RouteLabPage";

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

describe("RouteLabPage", () => {
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
