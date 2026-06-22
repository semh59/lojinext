import { describe, expect, it } from "vitest";
import { render, screen } from "../../../test/test-utils";
import {
  RouteHeatmap,
  colorForConsumption,
  projectPoint,
} from "../RouteHeatmap";
import type { SegmentSim } from "../../../api/route-sim";

function seg(overrides: Partial<SegmentSim>): SegmentSim {
  return {
    seq: 0,
    length_km: 0.5,
    grade_pct: 1,
    road_class: "motorway",
    sim_speed_kmh: 80,
    sim_l_per_100km: 30,
    sim_l_total: 0.15,
    eta_sec: 20,
    mid_lon: 29.0,
    mid_lat: 41.0,
    maxspeed_kmh: 90,
    traffic_speed_kmh: 80,
    congestion: "low",
    speed_source: "traffic",
    ...overrides,
  };
}

describe("colorForConsumption", () => {
  it("maps L/100km to green/amber/red thresholds", () => {
    expect(colorForConsumption(25)).toBe("#22c55e");
    expect(colorForConsumption(29.99)).toBe("#22c55e");
    expect(colorForConsumption(30)).toBe("#f59e0b");
    expect(colorForConsumption(39.99)).toBe("#f59e0b");
    expect(colorForConsumption(40)).toBe("#ef4444");
    expect(colorForConsumption(55)).toBe("#ef4444");
  });
});

describe("projectPoint", () => {
  const b = { minLon: 28, maxLon: 30, minLat: 40, maxLat: 42 };
  it("maps min/max corners into padded viewBox (lat inverted)", () => {
    const min = projectPoint(28, 42, b); // minLon, maxLat → top-left
    const max = projectPoint(30, 40, b); // maxLon, minLat → bottom-right
    expect(min.x).toBeLessThan(max.x);
    expect(min.y).toBeLessThan(max.y); // maxLat at top (small y)
  });
});

describe("RouteHeatmap", () => {
  it("renders an svg with segment lines when coords present", () => {
    const segs = [
      seg({ seq: 0, mid_lon: 29.0, mid_lat: 41.0 }),
      seg({ seq: 1, mid_lon: 29.1, mid_lat: 41.1, sim_l_per_100km: 45 }),
      seg({ seq: 2, mid_lon: 29.2, mid_lat: 41.2 }),
    ];
    const { container } = render(<RouteHeatmap segments={segs} />);
    expect(container.querySelector("svg")).toBeTruthy();
    // n-1 lines for n points
    expect(container.querySelectorAll("line").length).toBe(2);
  });

  it("shows empty state when no coords", () => {
    const segs = [seg({ mid_lon: null, mid_lat: null })];
    render(<RouteHeatmap segments={segs} />);
    expect(screen.getByText(/segment koordinatı yok/i)).toBeTruthy();
  });
});
