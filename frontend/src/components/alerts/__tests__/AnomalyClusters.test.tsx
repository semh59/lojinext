/**
 * 0-mock epiği: alerts domain. `anomalyService.getClusters` orval-generated
 * client (`getAnomalyClustersApiV1AnomaliesClustersGet`) üzerinden gidiyor
 * — baseURL origin-only olmalı (REAL_BACKEND_ORIGIN), REAL_BACKEND_URL değil.
 *
 * Orijinal dosyanın TEK testi "3 adet high tüketim anomalisi" etiketli,
 * non-empty bir cluster listesi render ediyordu. Bu, anomali kümeleme
 * pipeline'ının (ML tabanlı, gerçek sefer/GPS verisinden RCA ile üretilir)
 * gerçek veri üretmesini gerektirir — anomaliler frontend'in erişebildiği
 * hiçbir API yüzeyinden doğrudan create edilemiyor (bkz
 * `POST /admin/investigations` → `anomaly_id` FK kontrolü var, anomali
 * kaydı olmadan investigation bile açılamıyor; anomalilerin kendisi için
 * hiç create endpoint'i yok — sadece ML pipeline / seed script üretir).
 * Çalıştığım gerçek backend'de `GET /anomalies/clusters?days=30` boş liste
 * döndürüyor (doğrulandı: `{"clusters":[],"period_days":30}`). Bu yüzden
 * non-empty-cluster testi gerçek backend'e çevrilemiyor; onun yerine gerçek
 * backend'e karşı GERÇEK boş-durum davranışını (`alerts.clusters_none`)
 * doğrulayan bir test yazıldı — bu hâlâ gerçek bir entegrasyon noktası
 * (useQuery → anomalyService.getClusters → gerçek HTTP → gerçek boş yanıt).
 */
import { describe, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("AnomalyClusters (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let AnomalyClusters: typeof import("../AnomalyClusters").AnomalyClusters;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ render, screen } = await import("../../../test/test-utils"));
    ({ AnomalyClusters } = await import("../AnomalyClusters"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("gerçek backend boş küme listesi döndürdüğünde 'anlamlı desen yok' mesajı gösterilir", async () => {
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token); // AuthContext'in olası /auth/me 404 temizlemesine karşı
    render(<AnomalyClusters />);

    await screen.findByText(
      /Son 30 günde anlamlı bir anomali deseni yok\./,
      {},
      { timeout: 10000 },
    );
  }, 15000);
});
