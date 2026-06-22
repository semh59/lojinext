import { describe, expect, it } from "vitest";

import { buildTripImpactRequest } from "../../../lib/route-weather";

describe("buildTripImpactRequest", () => {
  it("builds a weather request from route coordinates", () => {
    const result = buildTripImpactRequest(
      {
        cikis_lat: 41.07,
        cikis_lon: 28.54,
        varis_lat: 39.96,
        varis_lon: 32.74,
      } as any,
      "2026-03-19",
    );

    expect(result).toEqual({
      cikis_lat: 41.07,
      cikis_lon: 28.54,
      varis_lat: 39.96,
      varis_lon: 32.74,
      trip_date: "2026-03-19",
    });
  });

  it("returns null when route coordinates are incomplete", () => {
    const result = buildTripImpactRequest(
      {
        cikis_lat: 41.07,
        cikis_lon: 28.54,
      } as any,
      "2026-03-19",
    );

    expect(result).toBeNull();
  });
});
