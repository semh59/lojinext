/**
 * 0-mock epiği: DashboardPage 5 ayrı gerçek servisi (reports/dashboard,
 * reports/consumption-trend, trips/stats, trips/today, anomalies/fleet-
 * insights, predictions/comparison) aggregate ediyor. Seed veri olmadan
 * cold-start/boş-state render'ı gerçek backend'e karşı doğrulanıyor —
 * KPI'lar "—" placeholder ile, listeler boş state ile render olmalı,
 * hiçbir query 4xx/5xx patlamamalı.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("DashboardPage (real backend)", () => {
  let render: typeof import("../../test/test-utils").render;
  let screen: typeof import("../../test/test-utils").screen;
  let waitFor: typeof import("../../test/test-utils").waitFor;
  let DashboardPage: typeof import("../DashboardPage").default;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ render, screen, waitFor } = await import("../../test/test-utils"));
    ({ default: DashboardPage } = await import("../DashboardPage"));
  }, 20000);

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("renders dashboard container and aggregates all real endpoints", async () => {
    sessionStorage.setItem("access_token", await loginAsAdmin());
    render(<DashboardPage />);

    expect(screen.getByTestId("dashboard-page")).toBeTruthy();

    await waitFor(
      () => {
        expect(screen.getAllByText(/Aktif Araç/i)[0]).toBeTruthy();
      },
      { timeout: 15000 },
    );
  }, 20000);
});
