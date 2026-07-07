/**
 * 0-mock epiği — son parti. tripService (bulkDelete/uploadExcel/
 * getFuelPerformance/getTimeline) gerçek backend'e karşı.
 *
 * getTimeline dönüşümü sırasında GERÇEK bir bug bulundu+düzeltildi:
 * `api/trips.ts`'in eski `getTimeline` implementasyonu backend'in
 * `TripTimelineResponse` ({items: [...]}) cevabını doğrudan
 * `SeferTimelineItem[]` olarak cast ediyordu — TripFormModal.tsx bu değeri
 * doğrudan bir array state'ine (`setTimeline`) veriyordu, yani gerçekte
 * timeline sekmesi hep bir obje alıyordu, dizi değil. Kaynak `.items`'ı
 * unwrap edecek şekilde düzeltildi.
 */
import axios from "axios";
import { describe, it, expect, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("tripService contract (real backend)", () => {
  let tripService: typeof import("../../../api/trips").tripService;
  let token: string;
  let aracId: number;
  let soforId: number;
  let seferId: number;

  beforeAll(async () => {
    // Sıra ÖNEMLİ: stubEnv, loginAsAdmin'dan ÖNCE gelmeli — loginAsAdmin
    // (lazy sanitizer kurulumu için) axios-instance'ı import eder ve
    // axios-instance baseURL'i modül yüklenirken import.meta.env'den okur;
    // stub'dan önce yüklenirse tüm istekler jsdom origin'ine gidip network
    // hatasıyla düşer (2026-07-07 seri koşumda canlı yakalandı).
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ tripService } = await import("../../../api/trips"));

    const headers = { Authorization: `Bearer ${token}` };
    const runTag = Date.now();

    const vehicle = await axios.post(
      `${REAL_BACKEND_URL}/vehicles/`,
      { plaka: `34FZ${runTag % 10000}`, marka: "Faz2TestMarka" },
      { headers },
    );
    aracId = vehicle.data.id;

    const driver = await axios.post(
      `${REAL_BACKEND_URL}/drivers/`,
      { ad_soyad: `Faz2TripDriver${runTag}`, ehliyet_sinifi: "E" },
      { headers },
    );
    soforId = driver.data.id;

    const trip = await axios.post(
      `${REAL_BACKEND_URL}/trips/`,
      {
        tarih: "2026-07-01",
        arac_id: aracId,
        sofor_id: soforId,
        cikis_yeri: `Faz2Cikis${runTag}`,
        varis_yeri: `Faz2Varis${runTag}`,
        mesafe_km: 450,
        net_kg: 5000,
      },
      { headers },
    );
    seferId = trip.data.id;
  });

  afterAll(async () => {
    const headers = { Authorization: `Bearer ${token}` };
    await axios
      .delete(`${REAL_BACKEND_URL}/trips/${seferId}`, { headers })
      .catch(() => undefined);
    await axios
      .delete(`${REAL_BACKEND_URL}/drivers/${soforId}`, { headers })
      .catch(() => undefined);
    await axios
      .delete(`${REAL_BACKEND_URL}/drivers/${soforId}`, { headers })
      .catch(() => undefined);
    await axios
      .delete(`${REAL_BACKEND_URL}/vehicles/${aracId}`, { headers })
      .catch(() => undefined);
    await axios
      .delete(`${REAL_BACKEND_URL}/vehicles/${aracId}`, { headers })
      .catch(() => undefined);
    vi.unstubAllEnvs();
  });

  it("bulkDelete sends only the { sefer_ids } body contract to the real endpoint", async () => {
    const result = await tripService.bulkDelete([999001, 999002]);

    expect(result.success_count).toBe(0);
    expect(result.failed_count).toBe(2);
    expect(result.failed.length).toBe(2);
  }, 15000);

  it("uploadExcel returns canonical upload response fields for a real .xlsx", async () => {
    const templateResp = await axios.get(
      `${REAL_BACKEND_URL}/trips/excel/template`,
      {
        headers: { Authorization: `Bearer ${token}` },
        responseType: "arraybuffer",
      },
    );
    const file = new File([templateResp.data], "trips.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    const result = await tripService.uploadExcel(file);

    expect(result).toHaveProperty("success");
    expect(result).toHaveProperty("total_rows");
    expect(result).toHaveProperty("success_count");
    expect(result).toHaveProperty("failed_count");
    expect(Array.isArray(result.errors)).toBe(true);
  }, 20000);

  it("getFuelPerformance passes cleaned filters and returns real API payload", async () => {
    const result = await tripService.getFuelPerformance({
      durum: "",
      baslangic_tarih: "2026-01-01",
      bitis_tarih: "2026-12-31",
    } as any);

    expect(result).toHaveProperty("kpis");
    expect(result).toHaveProperty("trend");
    expect(result).toHaveProperty("outliers");
    expect(typeof result.low_data).toBe("boolean");
  }, 15000);

  it("getTimeline returns a real timeline array (unwrapped from {items})", async () => {
    const result = await tripService.getTimeline(seferId);

    expect(Array.isArray(result)).toBe(true);
  }, 15000);
});
