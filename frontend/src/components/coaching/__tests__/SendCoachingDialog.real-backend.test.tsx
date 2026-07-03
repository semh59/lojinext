/**
 * 0-mock epiği (coaching domain): SendCoachingDialog.test.tsx'in 3 saf
 * render senaryosuna ek olarak, gerçek backend'e karşı 2 senaryo:
 * - 409 "Telegram'a kayıtlı değil": telegram_id'siz gerçek bir şoför
 *   (API üzerinden oluşturulur, seed gerektirmez) ile gerçek 409
 *   tetiklenir; POST /coaching/{id}/send bu durumda Telegram'a HİÇ
 *   istek atmıyor (app/api/v1/endpoints/coaching.py — telegram_id
 *   kontrolü Telegram HTTP çağrısından ÖNCE).
 * - "Başarılı gönderim": backend'in send_coaching endpoint'i GERÇEK
 *   Telegram Bot API'sine (https://api.telegram.org) canlı bir istek
 *   atıyor (httpx.AsyncClient ile doğrudan sendMessage). Bunu tetiklemek
 *   hem gerçek bir dış-servis yan etkisi hem de public API'den
 *   telegram_id'li bir şoför oluşturmanın mümkün olmaması (POST
 *   /drivers/ endpoint'i SoforCreate.telegram_id alanını
 *   service.add_sofor(...)'a hiç iletmiyor — ayrı, kapsam dışı bir
 *   bulgu) nedeniyle DOKÜMANTE mock'lu kalıyor: coachingService.send
 *   üzerinde vi.spyOn (tek test, sonda restore edilir), diğer testler
 *   gerçek HTTP kullanmaya devam ediyor.
 *
 * NotificationContext hâlâ mock'lu: test-utils.tsx'teki AllTheProviders
 * NotificationProvider içermiyor (useNotify Provider dışında çağrılırsa
 * throw eder) — bu backend'den bağımsız, saf bir test-altyapısı gereği,
 * "harmless UI-lib mock" kategorisinde (bkz görev talimatı madde 4).
 */
import {
  describe,
  expect,
  it,
  vi,
  beforeAll,
  afterAll,
  afterEach,
} from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

vi.mock("../../../context/NotificationContext", async () => {
  const actual = await vi.importActual<any>(
    "../../../context/NotificationContext",
  );
  return {
    ...actual,
    useNotify: () => ({ notify: notifyMock }),
  };
});

const notifyMock = vi.fn();

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("SendCoachingDialog (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let SendCoachingDialog: typeof import("../SendCoachingDialog").SendCoachingDialog;
  let coachingService: typeof import("../../../api/coaching").coachingService;
  let authToken: string;
  let driverId: number;
  const driverName = `ZM SendCoaching Test ${Date.now()}`;

  const INSIGHT = {
    category: "yakit_yonetimi" as const,
    pattern: "Pattern",
    evidence: ["e1"],
    suggestion: "Rölantide bekleme süresini azaltın.",
    impact_score: 0.4,
  };

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, fireEvent, waitFor } = await import(
      "../../../test/test-utils"
    ));
    ({ SendCoachingDialog } = await import("../SendCoachingDialog"));
    ({ coachingService } = await import("../../../api/coaching"));

    // telegram_id'siz gerçek bir şoför — 409 senaryosunu Telegram'a hiç
    // dokunmadan tetikler.
    const createResp = await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/drivers/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({ ad_soyad: driverName, aktif: true }),
    });
    const created = await createResp.json();
    driverId = created.id;
  });

  afterEach(() => {
    notifyMock.mockClear();
    vi.restoreAllMocks();
  });

  afterAll(async () => {
    if (driverId) {
      await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/drivers/${driverId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${authToken}` },
      }).catch(() => {});
    }
    vi.unstubAllEnvs();
  });

  it("telegram_id'siz şoför → gerçek backend 409 → 'kayıtlı değil' uyarısı", async () => {
    sessionStorage.setItem("access_token", authToken); // AuthProvider temizlemesine karşı
    render(
      <SendCoachingDialog
        soforId={driverId}
        soforAdi={driverName}
        insight={INSIGHT}
        onClose={vi.fn()}
      />,
    );
    sessionStorage.setItem("access_token", authToken);
    fireEvent.click(screen.getByRole("button", { name: /Gönder/ }));

    await waitFor(
      () =>
        expect(notifyMock).toHaveBeenCalledWith(
          "warning",
          "Şoför Telegram'a kayıtlı değil",
          "Bu şoför Telegram bot ile eşleşmemiş; mesaj gönderilemez.",
        ),
      { timeout: 10000 },
    );
  }, 15000);

  it("başarılı gönderim (dokümante mock — gerçek Telegram API yan etkisinden kaçınmak için) → onClose çağrılır", async () => {
    const sendSpy = vi.spyOn(coachingService, "send").mockResolvedValue({
      sent: true,
      delivery_id: 42,
      channel: "telegram",
      sent_at: new Date().toISOString(),
    });

    sessionStorage.setItem("access_token", authToken);
    const onClose = vi.fn();
    render(
      <SendCoachingDialog
        soforId={driverId}
        soforAdi={driverName}
        insight={INSIGHT}
        onClose={onClose}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Gönder/ }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(sendSpy).toHaveBeenCalledWith(
      driverId,
      INSIGHT.suggestion,
      "yakit_yonetimi",
    );
  });
});
