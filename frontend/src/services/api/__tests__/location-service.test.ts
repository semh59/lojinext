/**
 * 0-mock epiği Faz 2: gerçek, izole bir backend'e (uvicorn + test DB + api_stub)
 * karşı gerçek HTTP round-trip. vi.mock(axios-instance/orval-mutator) yerine
 * `VITE_API_URL`'i gerçek backend'e işaret edecek şekilde stub'layıp
 * locationService'i dinamik import ediyoruz (modül top-level'da
 * import.meta.env.VITE_API_URL'i okuyor, bu yüzden import'tan ÖNCE stub
 * gerekiyor). Backend erişilemezse suit sessizce skip edilir.
 */
import { describe, it, expect, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("locationService (real backend)", () => {
  let locationService: typeof import("../../../api/locations").locationService;
  let createdId: number | undefined;
  // Unique per test run so repeated local runs don't collide with the
  // real DB's uq_cikis_varis constraint (a stray row from a prior run
  // would 400 on re-create otherwise — this bit a first draft of this test).
  const runTag = Date.now();

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ locationService } = await import("../../../api/locations"));
  });

  afterAll(async () => {
    if (createdId) {
      // Soft-delete then hard-delete (2nd call on an already-inactive row
      // hard-deletes — same real endpoint semantics exercised elsewhere
      // in this epic's backend tests) so repeated runs stay collision-free.
      await locationService.delete(createdId).catch(() => undefined);
      await locationService.delete(createdId).catch(() => undefined);
    }
    vi.unstubAllEnvs();
  });

  it("getAll should fetch real locations with pagination shape", async () => {
    const result = await locationService.getAll({ limit: 10, skip: 0 });

    expect(result).toHaveProperty("items");
    expect(result).toHaveProperty("total");
    expect(Array.isArray(result.items)).toBe(true);
  });

  it("create should persist a new location for real", async () => {
    const newLoc = {
      cikis_yeri: `Faz2TestA${runTag}`,
      varis_yeri: `Faz2TestB${runTag}`,
      mesafe_km: 123.4,
    };

    const result = await locationService.create(newLoc as any);
    createdId = (result as any).id;

    // Backend normalizes place names via _tr_title (Turkish-aware title
    // case, real behavior fixed earlier in this epic): first letter stays
    // as-is (uppercased), rest lowercased — "Faz2TestA123" -> "Faz2testa123".
    const expectedName = `Faz2testa${runTag}`;
    expect(createdId).toBeGreaterThan(0);
    expect((result as any).cikis_yeri).toBe(expectedName);

    // Real round-trip: the row is really there via getById.
    const fetched = await locationService.getById(createdId!);
    expect((fetched as any).id).toBe(createdId);
  });

  it("geocode should return real ORS-stub suggestions", async () => {
    const result = await locationService.geocode("Hadimkoy Lojistik");

    expect(Array.isArray(result)).toBe(true);
    expect(result[0].label).toBe("Hadimkoy Lojistik");
    expect(result[0].source).toBe("ors");
  });

  it("getRouteInfo should fetch real route info and serve repeat lookups from cache", async () => {
    const coords = {
      cikis_lat: 41,
      cikis_lon: 29,
      varis_lat: 40,
      varis_lon: 32,
    };

    // Hermetiklik: eski sürüm İLK çağrıda source === "cache" bekliyordu —
    // bu, başka bir test dosyasının/backend integration suit'inin aynı
    // koordinatları ÖNCEDEN sorgulayıp route cache'ini doldurmuş olmasına
    // (koşum-sırası bağımlılığı) güveniyordu; boş bir CI DB'sinde ilk çağrı
    // "api" döner ve test kırılırdı. Testi kendi içinde bağımsızlaştır:
    // ilk çağrı cache'i doldurur (kirli DB'de zaten "cache" dönebilir, bu
    // yüzden source'una assert edilmez), ikinci çağrı HER durumda gerçek
    // cache-hit olmalıdır.
    const first = await locationService.getRouteInfo(coords);
    expect(first).toHaveProperty("distance_km");

    const second = await locationService.getRouteInfo(coords);
    expect(second).toHaveProperty("distance_km");
    expect((second as any).source).toBe("cache");
  });
});
