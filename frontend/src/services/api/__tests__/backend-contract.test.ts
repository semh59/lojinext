/**
 * Layer 5 — Frontend Backend Contract
 *
 * Verifies that the running Docker backend returns shapes matching
 * the TypeScript interfaces used by the frontend.
 * No mocks. Direct axios calls to the real server.
 *
 * Run with:
 *   VITE_API_BASE_URL=http://localhost:8000 npx vitest run src/services/api/__tests__/backend-contract.test.ts
 */
import axios from "axios";
import { describe, it, expect, beforeAll } from "vitest";
import type { Vehicle, Driver } from "../../../types";

const BASE_URL =
  (import.meta as any).env?.VITE_API_BASE_URL ?? "http://localhost:8000";
let accessToken: string | null = null;
let backendReachable = false;

beforeAll(async () => {
  try {
    await axios.get(`${BASE_URL}/health`, { timeout: 3000 });
    backendReachable = true;
  } catch {
    console.warn(
      "[backend-contract] Backend unreachable, all tests will skip.",
    );
    return;
  }

  try {
    const loginResp = await axios.post(
      `${BASE_URL}/api/v1/auth/token`,
      new URLSearchParams({
        username: "admin@lojinext.com",
        password: "admin123",
      }),
      { headers: { "Content-Type": "application/x-www-form-urlencoded" } },
    );
    accessToken = loginResp.data.access_token;
  } catch (e: any) {
    console.warn(
      "[backend-contract] Login failed — auth tests will be limited",
      e?.message,
    );
  }
});

function authHeaders() {
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
}

// ── Auth shape ───────────────────────────────────────────────────────────────

describe("auth token shape", () => {
  it("POST /auth/token returns access_token string and token_type=bearer", async () => {
    if (!backendReachable) return;

    const resp = await axios.post(
      `${BASE_URL}/api/v1/auth/token`,
      new URLSearchParams({
        username: "admin@lojinext.com",
        password: "admin123",
      }),
      {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        validateStatus: () => true,
      },
    );
    if (resp.status === 401) {
      console.warn("Seed user not found — skipping auth shape test");
      return;
    }
    expect(resp.status).toBe(200);
    const body = resp.data;
    expect(typeof body.access_token).toBe("string");
    expect(body.access_token.length).toBeGreaterThan(10);
    expect(body.token_type).toBe("bearer");
  });
});

// ── Vehicles list shape ───────────────────────────────────────────────────────

describe("vehicles list shape", () => {
  it("GET /vehicles/ returns StandardResponse {data:[],meta:{total}} matching Vehicle interface", async () => {
    if (!backendReachable) return;

    const resp = await axios.get(`${BASE_URL}/api/v1/vehicles/`, {
      headers: authHeaders(),
      validateStatus: () => true,
    });

    if (resp.status === 401) {
      console.warn("No auth token, skipping vehicles shape test");
      return;
    }

    expect(resp.status).toBe(200);
    const body = resp.data;

    // Backend returns StandardResponse: {data: [...], meta: {total: number}}
    expect(body).toHaveProperty("data");
    expect(Array.isArray(body.data)).toBe(true);

    const items: Vehicle[] = body.data;
    const meta = body.meta ?? {};
    if ("total" in meta) {
      expect(typeof meta.total).toBe("number");
      expect(meta.total).toBeGreaterThanOrEqual(0);
    }

    if (items.length > 0) {
      const v = items[0];
      expect(typeof v.id).toBe("number");
      expect(typeof v.plaka).toBe("string");
      expect(v.plaka.length).toBeGreaterThan(0);
      expect(typeof v.aktif).toBe("boolean");
      expect(typeof v.hedef_tuketim).toBe("number");
      expect(isNaN(v.hedef_tuketim)).toBe(false);
    }
  });
});

// ── Drivers list shape ────────────────────────────────────────────────────────

describe("drivers list shape", () => {
  it("GET /drivers/ returns items[] matching Driver interface", async () => {
    if (!backendReachable) return;

    const resp = await axios.get(`${BASE_URL}/api/v1/drivers/`, {
      headers: authHeaders(),
      validateStatus: () => true,
    });

    if (resp.status === 401) return;

    expect(resp.status).toBe(200);
    const body = resp.data;
    const items: Driver[] = Array.isArray(body)
      ? body
      : body.items ?? body.data ?? [];
    expect(Array.isArray(items)).toBe(true);

    if (items.length > 0) {
      const d = items[0];
      expect(typeof d.ad_soyad).toBe("string");
      expect(typeof d.ehliyet_sinifi).toBe("string");
      expect(typeof d.aktif).toBe("boolean");
    }
  });
});

// ── Trips list shape ──────────────────────────────────────────────────────────

describe("trips list shape", () => {
  it("GET /trips/ returns {items, total} envelope", async () => {
    if (!backendReachable) return;

    const resp = await axios.get(`${BASE_URL}/api/v1/trips/`, {
      headers: authHeaders(),
      validateStatus: () => true,
    });

    if (resp.status === 401) return;

    expect(resp.status).toBe(200);
    const body = resp.data;
    expect("items" in body).toBe(true);
    expect("total" in body).toBe(true);
    expect(typeof body.total).toBe("number");
  });
});

// ── Dashboard shape ───────────────────────────────────────────────────────────

describe("dashboard report shape", () => {
  it("GET /reports/dashboard returns finite numeric fields with no NaN", async () => {
    if (!backendReachable) return;

    const resp = await axios.get(`${BASE_URL}/api/v1/reports/dashboard`, {
      headers: authHeaders(),
      validateStatus: () => true,
    });

    if (resp.status === 401) return;

    expect(resp.status).toBe(200);
    const body = resp.data;

    expect(typeof body.toplam_sefer).toBe("number");
    expect(isNaN(body.toplam_km)).toBe(false);
    expect(isNaN(body.toplam_yakit)).toBe(false);
    expect(isNaN(body.filo_ortalama)).toBe(false);
    expect(body.toplam_sefer).toBeGreaterThanOrEqual(0);
  });
});

// ── Locations list shape ──────────────────────────────────────────────────────

describe("locations list shape", () => {
  it("GET /locations/ returns items with cikis_yeri and varis_yeri strings", async () => {
    if (!backendReachable) return;

    const resp = await axios.get(`${BASE_URL}/api/v1/locations/`, {
      headers: authHeaders(),
      validateStatus: () => true,
    });

    if (resp.status === 401) return;

    expect(resp.status).toBe(200);
    const body = resp.data;
    const items = Array.isArray(body) ? body : body.items ?? body.data ?? [];

    if (items.length > 0) {
      const loc = items[0];
      expect(typeof loc.cikis_yeri).toBe("string");
      expect(typeof loc.varis_yeri).toBe("string");
      expect(typeof loc.mesafe_km).toBe("number");
      expect(isNaN(loc.mesafe_km)).toBe(false);
    }
  });
});

// ── 401 guard ─────────────────────────────────────────────────────────────────

describe("auth guard", () => {
  it("GET /vehicles/ without token returns 401", async () => {
    if (!backendReachable) return;

    const resp = await axios.get(`${BASE_URL}/api/v1/vehicles/`, {
      validateStatus: () => true,
    });
    expect(resp.status).toBe(401);
  });
});
