import { describe, expect, it, vi } from "vitest";

vi.mock("recharts", () => ({
  ComposedChart: ({ children }: any) => (
    <div data-testid="chart">{children}</div>
  ),
  Line: () => <div data-testid="line" />,
  Area: () => <div data-testid="area" />,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
}));

import { render, screen } from "../../../test/test-utils";
import { RouteProfileChart, buildProfile } from "../RouteProfileChart";
import type { SegmentSim } from "../../../api/route-sim";

function seg(seq: number, len: number, l: number): SegmentSim {
  return {
    seq,
    length_km: len,
    grade_pct: 2,
    road_class: "primary",
    sim_speed_kmh: 70,
    sim_l_per_100km: l,
    sim_l_total: 0.1,
    eta_sec: 25,
    mid_lon: 29,
    mid_lat: 41,
    maxspeed_kmh: null,
    traffic_speed_kmh: null,
    congestion: "low",
    speed_source: "road_class",
  };
}

describe("buildProfile", () => {
  it("accumulates distance along segments", () => {
    const p = buildProfile([seg(0, 0.5, 30), seg(1, 0.5, 32), seg(2, 1.0, 28)]);
    expect(p.map((x) => x.km)).toEqual([0.5, 1.0, 2.0]);
    expect(p[1].consumption).toBe(32);
  });
});

describe("RouteProfileChart", () => {
  it("renders the chart with speed + consumption lines", () => {
    render(<RouteProfileChart segments={[seg(0, 0.5, 30), seg(1, 0.5, 35)]} />);
    expect(screen.getByTestId("chart")).toBeTruthy();
    expect(screen.getAllByTestId("line").length).toBe(2);
  });
});
