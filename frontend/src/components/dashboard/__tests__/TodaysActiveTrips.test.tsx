/**
 * 0-mock epiği Faz 2: `TodaysActiveTrips` widget'ının durum-etiketi çeviri
 * mantığı (Planned/Completed/Cancelled -> Planlandı/Tamamlandı/İptal, bkz.
 * `tripStatusMetaFor` in ../TodaysActiveTrips.tsx) artık gerçek backend'e
 * karşı test ediliyor. Gerçek bir araç + şoför + iki gerçek Sefer (biri
 * Planned kalıyor, diğeri `/trips/bulk/status` ile Completed'e taşınıyor)
 * oluşturulup `GET /trips/today` üzerinden okunuyor.
 *
 * "Cancelled" durumu ve "gerçekten bilinmeyen bir durum" (fallback rozeti)
 * senaryoları BU dosyada YOK — ikisi de gerçek backend'den elde
 * edilemiyor:
 *  - Backend'in `SeferReadService.get_all_paged` metodu `aktif_only=True`
 *    varsayılanıyla çalışıyor ve `/trips/bulk/cancel` bir seferi
 *    iptal ettiğinde onu aktif=false yapıyor — bu yüzden iptal edilmiş bir
 *    sefer `/trips/today`'in `items` dizisinde asla görünmüyor (canlı
 *    curl ile doğrulandı: bulk/cancel sonrası `items: []` ama
 *    `meta.total: 1` — backend'in kendi total/items tutarsızlığı, bu
 *    dosyanın kapsamı dışı bir backend konusu).
 *  - `TripStatus` DB CHECK constraint + Pydantic enum'u yalnızca
 *    Planned/Completed/Cancelled kabul eder; gerçek backend hiçbir zaman
 *    "TotallyUnknownStatus" gibi bilinmeyen bir durum dönemez.
 *
 * Bu iki senaryo, mock'lu haliyle sibling
 * `TodaysActiveTrips.mocked-fallback.test.tsx` dosyasında kalıyor (gerçek
 * backend describe bloğu ile hoisted `vi.mock` aynı dosyada karışamaz).
 */
import { describe, expect, it, beforeAll, afterAll } from "vitest";
import axios from "axios";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_URL,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("TodaysActiveTrips (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let TodaysActiveTrips: typeof import("../TodaysActiveTrips").TodaysActiveTrips;
  let authToken: string;

  const tag = Date.now();
  // NOT: `toISOString()` UTC tarihini döner — backend'in "bugün" filtresi
  // sunucunun YEREL saatine göre çalışıyor (Python `date.today()`). Bu
  // ikisi UTC+X bir zaman diliminde gece yarısına yakın saatlerde
  // (ör. yerel 00:05, UTC hâlâ bir önceki gün 21:05) FARKLI günlere denk
  // gelebiliyor — tam olarak bu koşum sırasında yakalandı (gerçek bir test
  // flake'i, backend/production kodunda değil). Yerel tarihi elle inşa et.
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(
    2,
    "0",
  )}-${String(now.getDate()).padStart(2, "0")}`;
  const seferNoPlanned = `E2E-TAT-PLANNED-${tag}`;
  const seferNoCompleted = `E2E-TAT-COMPLETED-${tag}`;
  let vehicleId: number | undefined;
  let driverId: number | undefined;
  let plannedTripId: number | undefined;
  let completedTripId: number | undefined;

  const authHeaders = () => ({ Authorization: `Bearer ${authToken}` });

  beforeAll(async () => {
    // orval-generated client (readBugununSeferleriApiV1TripsTodayGet) path'i
    // zaten "/api/v1/trips/today" içeriyor -> baseURL SADECE origin olmalı.
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ TodaysActiveTrips } = await import("../TodaysActiveTrips"));

    const vehicleRes = await axios.post(
      `${REAL_BACKEND_URL}/vehicles/`,
      { plaka: `34 TAT${tag % 9000}`, marka: "TodaysTripsTestMarka" },
      { headers: authHeaders() },
    );
    vehicleId = vehicleRes.data.id;

    const driverRes = await axios.post(
      `${REAL_BACKEND_URL}/drivers/`,
      { ad_soyad: `TodaysTrips Test Driver ${tag}`, ehliyet_sinifi: "E" },
      { headers: authHeaders() },
    );
    driverId = driverRes.data.id;

    const locationsRes = await axios.get(
      `${REAL_BACKEND_URL}/locations/?limit=1`,
      { headers: authHeaders() },
    );
    const locationId = locationsRes.data.items[0].id as number;

    const createTrip = async (seferNo: string): Promise<number> => {
      const res = await axios.post(
        `${REAL_BACKEND_URL}/trips/`,
        {
          sefer_no: seferNo,
          tarih: today,
          arac_id: vehicleId,
          sofor_id: driverId,
          guzergah_id: locationId,
          bos_agirlik_kg: 8000,
          dolu_agirlik_kg: 18000,
          net_kg: 10000,
          cikis_yeri: "Istanbul",
          varis_yeri: "Ankara",
          mesafe_km: 450,
        },
        { headers: authHeaders() },
      );
      return res.data.id as number;
    };

    plannedTripId = await createTrip(seferNoPlanned);
    completedTripId = await createTrip(seferNoCompleted);

    await axios.patch(
      `${REAL_BACKEND_URL}/trips/bulk/status`,
      { sefer_ids: [completedTripId], new_status: "Completed" },
      { headers: authHeaders() },
    );
  }, 30000);

  afterAll(async () => {
    for (const id of [plannedTripId, completedTripId]) {
      if (id) {
        await axios
          .delete(`${REAL_BACKEND_URL}/trips/${id}`, {
            headers: authHeaders(),
          })
          .catch(() => {});
      }
    }
    if (vehicleId) {
      await axios
        .delete(`${REAL_BACKEND_URL}/vehicles/${vehicleId}`, {
          headers: authHeaders(),
        })
        .catch(() => {});
    }
    if (driverId) {
      await axios
        .delete(`${REAL_BACKEND_URL}/drivers/${driverId}`, {
          headers: authHeaders(),
        })
        .catch(() => {});
    }
    vi.unstubAllEnvs();
  });

  it("backend kanonik İngilizce durum değerlerini doğru Türkçe etikete çevirir", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<TodaysActiveTrips />);

    await waitFor(
      () =>
        expect(
          screen.getByText(new RegExp(seferNoPlanned)),
        ).toBeInTheDocument(),
      { timeout: 10000 },
    );
    expect(screen.getByText(new RegExp(seferNoCompleted))).toBeInTheDocument();

    // Eski Türkçe-anahtarlı sözlük bu değerlerle hiç eşleşmiyordu — ham
    // backend string'i ("Planned"/"Completed") ekranda çevrilmeden
    // görünüyordu. Fix sonrası doğru Türkçe etiketler basılır.
    expect(screen.getByText("Planlandı")).toBeInTheDocument();
    expect(screen.getByText("Tamamlandı")).toBeInTheDocument();

    // Ham backend string'lerinin ekranda kalmadığını da doğrula
    // (regresyon guard'ı — eski bug tam olarak buydu).
    expect(screen.queryByText("Planned")).not.toBeInTheDocument();
    expect(screen.queryByText("Completed")).not.toBeInTheDocument();
  }, 15000);
});
