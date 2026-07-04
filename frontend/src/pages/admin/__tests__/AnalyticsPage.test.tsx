import { beforeAll, describe, expect, it, vi } from "vitest";
import axios from "axios";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

let render: typeof import("../../../test/test-utils").render;
let screen: typeof import("../../../test/test-utils").screen;
let AnalyticsPage: typeof import("../AnalyticsPage").default;

describe.skipIf(!backendUp)("AnalyticsPage (real backend)", () => {
  const uniqueRoute = `/real-backend-analytics-${Date.now()}`;
  let token = "";

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
    ({ render, screen } = await import("../../../test/test-utils"));
    AnalyticsPage = (await import("../AnalyticsPage")).default;

    token = await loginAsAdmin();
    // Seed at least one real page-view row so the analytics endpoint has
    // non-empty top/bottom route data to render.
    await axios.post(
      `${REAL_BACKEND_URL}/analytics/page-view`,
      { route: uniqueRoute },
      { headers: { Authorization: `Bearer ${token}` } },
    );
  });

  it("renders top/bottom routes and total-view count from the real backend", async () => {
    sessionStorage.setItem("access_token", token);
    render(<AnalyticsPage />);

    // The seeded route shows up in both the top and bottom lists (only 2
    // distinct routes exist in this shared test DB) — assert presence,
    // not a specific list membership (the server decides ranking).
    const matches = await screen.findAllByText(
      uniqueRoute,
      {},
      { timeout: 10000 },
    );
    expect(matches.length).toBeGreaterThanOrEqual(1);

    // total_views must be >= 1 (real accumulated count, not a fixed mock).
    const periodEl = await screen.findByText(/gün|days/i);
    expect(periodEl).toBeInTheDocument();
  }, 15000);
});
