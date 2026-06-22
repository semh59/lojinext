import { describe, it, expect, vi, beforeEach } from "vitest";

const mockCustomAxios = vi.hoisted(() => vi.fn());
vi.mock("../../../lib/orval-mutator", () => ({
  customAxiosInstance: mockCustomAxios,
}));
vi.mock("../axios-instance", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

import { locationService } from "../../../api/locations";

describe("locationService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("getAll should fetch locations with filters", async () => {
    const mockData = { items: [], total: 0 };
    mockCustomAxios.mockResolvedValueOnce(mockData);

    const result = await locationService.getAll({ limit: 10, skip: 0 });

    expect(mockCustomAxios.mock.lastCall?.[0]).toMatchObject({
      url: "/api/v1/locations/",
      method: "GET",
    });
    expect(result).toEqual(mockData);
  });

  it("create should post new location", async () => {
    const newLoc = { cikis_yeri: "A", varis_yeri: "B", mesafe_km: 100 };
    const mockResponse = { id: 1, ...newLoc };
    mockCustomAxios.mockResolvedValueOnce(mockResponse);

    const result = await locationService.create(newLoc as any);

    expect(mockCustomAxios.mock.lastCall?.[0]).toMatchObject({
      url: "/api/v1/locations/",
      method: "POST",
    });
    expect(result).toEqual(mockResponse);
  });

  it("analyze should trigger route analysis", async () => {
    const mockAnalysis = { success: true, api_mesafe_km: 105 };
    mockCustomAxios.mockResolvedValueOnce(mockAnalysis);

    const result = await locationService.analyze(1);

    expect(mockCustomAxios.mock.lastCall?.[0]).toMatchObject({
      url: "/api/v1/locations/1/analyze",
      method: "POST",
    });
    expect(result).toEqual(mockAnalysis);
  });

  it("getRouteInfo should fetch info by coordinates", async () => {
    const coords = {
      cikis_lat: 41,
      cikis_lon: 29,
      varis_lat: 40,
      varis_lon: 32,
    };
    const mockInfo = { distance_km: 450 };
    mockCustomAxios.mockResolvedValueOnce(mockInfo);

    const result = await locationService.getRouteInfo(coords);

    expect(mockCustomAxios.mock.lastCall?.[0]).toMatchObject({
      url: "/api/v1/locations/route-info",
      method: "GET",
    });
    expect(result).toEqual(mockInfo);
  });

  it("geocode should fetch geocode suggestions", async () => {
    const mockSuggestions = [
      { lat: 41.07, lon: 28.54, label: "Hadimkoy Lojistik", source: "ors" },
    ];
    mockCustomAxios.mockResolvedValueOnce(mockSuggestions);

    const result = await locationService.geocode("Hadimkoy Lojistik");

    expect(mockCustomAxios.mock.lastCall?.[0]).toMatchObject({
      url: "/api/v1/locations/geocode",
      method: "GET",
    });
    expect(result).toEqual(mockSuggestions);
  });
});
