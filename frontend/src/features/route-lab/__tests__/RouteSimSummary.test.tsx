import { describe, expect, it } from "vitest";
import { render, screen } from "../../../test/test-utils";
import { RouteSimSummary } from "../RouteSimSummary";
import type { RouteSimResponse } from "../../../api/route-sim";

const result: RouteSimResponse = {
  simulation_id: 1,
  created_at: "2026-06-14T00:00:00Z",
  summary: {
    distance_km: 152.4,
    duration_min: 125,
    total_l: 48.3,
    avg_l_per_100km: 31.7,
    total_ascent_m: 334,
    total_descent_m: 424,
  },
  segments: [],
  raw_segment_count: 0,
  resampled_segment_count: 0,
  elevation_coverage_pct: 100,
  meta: {},
};

describe("RouteSimSummary", () => {
  it("renders summary stat values", () => {
    render(<RouteSimSummary result={result} />);
    expect(screen.getByText("152.4 km")).toBeTruthy();
    expect(screen.getByText("31.7 L/100km")).toBeTruthy();
    expect(screen.getByText("%100")).toBeTruthy();
    expect(screen.getByText("334 m")).toBeTruthy();
  });
});
