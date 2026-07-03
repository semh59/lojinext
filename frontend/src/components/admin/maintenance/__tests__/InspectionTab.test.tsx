/**
 * 0-mock epiği: InspectionTab hand-writes `axiosInstance.get(relativePath)`
 * calls (`/vehicles/inspection-alerts`, `/trailers/inspection-alerts`) — real,
 * documented endpoints (see CLAUDE.md "Muayene + kalibrasyon"). Converted to
 * hit the real backend instead of mocking axios-instance.
 *
 * The "expiring row" test needs a vehicle whose `muayene_tarihi` falls inside
 * the default 30-day window. The shared test DB starts empty, so we create
 * one real, uniquely-plated vehicle via a direct HTTP call in `beforeAll` and
 * hard-delete it in `afterAll` (idempotent — safe alongside parallel sibling
 * conversions hitting the same DB).
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_URL,
} from "../../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("InspectionTab (real backend)", () => {
  let render: typeof import("../../../../test/test-utils").render;
  let screen: typeof import("../../../../test/test-utils").screen;
  let InspectionTab: typeof import("../InspectionTab").InspectionTab;
  let authToken: string;
  let createdVehicleId: number | null = null;
  const plaka = `34 ZM ${Date.now() % 10000}`;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen } = await import("../../../../test/test-utils"));
    ({ InspectionTab } = await import("../InspectionTab"));

    const muayeneTarihi = new Date(Date.now() + 17 * 24 * 60 * 60 * 1000)
      .toISOString()
      .slice(0, 10);
    const resp = await fetch(`${REAL_BACKEND_URL}/vehicles/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({
        plaka,
        marka: "TESTMARKA",
        muayene_tarihi: muayeneTarihi,
      }),
    });
    const body = await resp.json();
    createdVehicleId = body.id ?? null;
  });

  afterAll(async () => {
    if (createdVehicleId != null) {
      await fetch(`${REAL_BACKEND_URL}/vehicles/${createdVehicleId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${authToken}` },
      });
    }
    vi.unstubAllEnvs();
  });

  it("renders vehicle + trailer inspection sections", () => {
    sessionStorage.setItem("access_token", authToken);
    render(<InspectionTab />);
    expect(screen.getByText("Araçlar")).toBeInTheDocument();
    expect(screen.getByText("Dorseler")).toBeInTheDocument();
  });

  it("shows an expiring inspection row for the real seeded vehicle", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<InspectionTab />);
    expect(
      await screen.findAllByText(plaka, {}, { timeout: 10000 }),
    ).not.toHaveLength(0);
  }, 15000);
});
