/**
 * 0-mock epiği: usePushNotifications.test.ts'in mock'lu senaryolarına ek
 * olarak, gerçek backend'e karşı çalışan bir sürüm. Browser Push API'leri
 * (Notification/PushManager/serviceWorker) hâlâ jsdom stub'ları ile
 * sağlanıyor — bunlar gerçek bir tarayıcı gerektirir, backend'in parçası
 * değil. `pushService` (getVapidPublicKey/subscribe) MOCK'LANMIYOR — gerçek
 * GET /push/vapid-public-key ve POST /push/subscribe çağrıları yapılır.
 *
 * Bu test dosyası ayrıca 0-mock epiği sırasında bulunan gerçek bir backend
 * hatasını doğrulamıştı: sentetik (break-glass) süper admin hesabı (id<=0,
 * kullanicilar tablosunda gerçek satırı yok) POST /push/subscribe çağırınca
 * eskiden yakalanmamış bir FK-violation 500 dönüyordu
 * (push_subscriptions.user_id_fkey), app/api/v1/endpoints/push.py bunun
 * için erken bir 403 döner hale getirilmişti.
 *
 * 2026-07-05 GÜNCELLEME: bu ortamda artık synthetic break-glass admin
 * DEĞİL, migration 0002'nin seed'lediği GERÇEK admin satırı (id=1,
 * `kullanicilar` tablosunda gerçek satırı var — ProfilePage.test.tsx ile
 * aynı karar) kullanılıyor. Bu kullanıcı için 403 senaryosu artık
 * tetiklenmiyor — `POST /push/subscribe` gerçek 201 döner (curl ile
 * kanıtlandı: `{"id":1,"endpoint":...}`). Bu yüzden bu test artık FK-
 * violation regresyonunu DEĞİL, gerçek admin için başarılı subscribe
 * akışını doğruluyor.
 *
 * Orijinal mock'lu dosya (usePushNotifications.test.ts) korunuyor: happy-path
 * subscribe başarı senaryosu, permission-denied, push_enabled=false ve
 * disable senaryoları — bunlar farklı backend yanıtları/rolleri gerektirir
 * ve gerçek backend'de sadece tek bir (sentetik admin) hesapla tekrarlanamaz.
 *
 * `usePushNotifications`'ın kendisi Router/QueryClient context'ine ihtiyaç
 * duymuyor (sade useState/useEffect) — bu yüzden burada test-utils'in
 * AllTheProviders sarmalayıcısı (gerçek AuthProvider dahil) YERİNE düz
 * `@testing-library/react`'ın renderHook'u kullanılıyor. Gerekçe: AllTheProviders
 * her renderHook'ta gerçek AuthProvider'ı da mount eder, o da mount anında
 * gerçek bir `/auth/me` isteği atar; bu istek bizim push çağrılarımızla
 * yarışınca axios-instance'ın PAYLAŞILAN modül-seviyeli `isRefreshing`/401-
 * refresh-fail akışını tetikleyip access_token'ı sessionStorage'dan siliyor
 * ve push çağrılarımızın da gerçek 403 yerine "Oturum süreniz doldu" hatası
 * almasına yol açıyordu (ampirik olarak doğrulandı — bu test dosyası
 * yazılırken keşfedildi, ayrı bir debug testiyle izole edildi). Router/
 * QueryClient'a ihtiyacı olmayan bir hook için gereksiz bir provider'ı
 * atlamak bu yarış durumunu tamamen ortadan kaldırıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../test/real-backend";

function setupBrowserMocks(opts: {
  permission?: NotificationPermission;
  requestResult?: NotificationPermission;
  existingSubscription?: PushSubscription | null;
  subscribeResult?: PushSubscription;
}) {
  const requestPermission = vi
    .fn()
    .mockResolvedValue(opts.requestResult ?? "granted");
  const getSubscription = vi
    .fn()
    .mockResolvedValue(opts.existingSubscription ?? null);
  const subscribe = vi.fn().mockResolvedValue(opts.subscribeResult ?? null);

  Object.defineProperty(global, "Notification", {
    configurable: true,
    value: { permission: opts.permission ?? "default", requestPermission },
  });

  Object.defineProperty(global, "PushManager", {
    configurable: true,
    value: class {},
  });

  Object.defineProperty(global.navigator, "serviceWorker", {
    configurable: true,
    value: {
      ready: Promise.resolve({
        pushManager: { getSubscription, subscribe },
      }),
    },
  });

  Object.defineProperty(global.navigator, "userAgent", {
    configurable: true,
    value: "TestUA",
  });

  return { requestPermission, getSubscription, subscribe };
}

const fakeSubscription = {
  endpoint: "https://push.example/real-backend-abc",
  toJSON: () => ({
    endpoint: "https://push.example/real-backend-abc",
    keys: { p256dh: "p256dh-key", auth: "auth-key" },
  }),
  unsubscribe: vi.fn().mockResolvedValue(true),
} as unknown as PushSubscription;

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("usePushNotifications (real backend)", () => {
  let renderHook: typeof import("@testing-library/react").renderHook;
  let waitFor: typeof import("@testing-library/react").waitFor;
  let usePushNotifications: typeof import("../usePushNotifications").usePushNotifications;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ renderHook, waitFor } = await import("@testing-library/react"));
    ({ usePushNotifications } = await import("../usePushNotifications"));
  }, 20000);

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("fetches the real VAPID public key and reports push_enabled", async () => {
    sessionStorage.setItem("access_token", authToken);
    setupBrowserMocks({ permission: "default" });

    const { pushService } = await import("../../api/push");
    const { public_key, push_enabled } = await pushService.getVapidPublicKey();

    expect(push_enabled).toBe(true);
    expect(typeof public_key).toBe("string");
    expect(public_key.length).toBeGreaterThan(0);
  }, 15000);

  it("enable() completes a real subscribe round-trip for the real admin account", async () => {
    sessionStorage.setItem("access_token", authToken);
    const browser = setupBrowserMocks({
      permission: "default",
      requestResult: "granted",
      subscribeResult: fakeSubscription,
    });

    const { result } = renderHook(() => usePushNotifications());
    await waitFor(
      () => {
        expect(result.current.supported).toBe(true);
      },
      { timeout: 10000 },
    );

    const { act } = await import("@testing-library/react");
    let ok = false;
    await act(async () => {
      ok = await result.current.enable();
    });

    expect(browser.requestPermission).toHaveBeenCalled();
    await waitFor(
      () => {
        expect(result.current.subscribed).toBe(true);
      },
      { timeout: 10000 },
    );
    expect(ok).toBe(true);
    expect(result.current.error).toBeNull();
  }, 15000);
});
