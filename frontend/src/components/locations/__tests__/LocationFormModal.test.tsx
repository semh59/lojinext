/**
 * 0-mock epiği Faz 2: `locationService.geocode`/`getRouteInfo` mock'ları
 * kaldırıldı — gerçek backend'e karşı gerçek UI etkileşimi (tip et →
 * geocode öneri gör → seç → route-info otomatik dolsun). api_stub'a bu
 * testin iki farklı arama metnini iki farklı koordinata çözecek şekilde
 * (Hadimkoy/Ostim) sentinel-metin senaryosu eklendi (bkz api_stub/main.py)
 * — aksi halde stub'ın varsayılan yanıtı her sorguya AYNI koordinatı
 * dönerdi ve bu test iki farklı geocode sonucunun gerçekten route-info'ya
 * doğru şekilde aktığını kanıtlayamazdı.
 */
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

// NOT: test-utils.tsx (act/fireEvent/render/screen/waitFor dahil TÜMÜ) burada
// SADECE dinamik import ile (beforeAll içinde, vi.stubEnv'DEN SONRA) alınır —
// bir STATİK import bile axios-instance.ts'in modül-seviyesi baseURL'ini
// stubEnv'den ÖNCE sabitler (Node modül cache'i aynı modülü ikinci kez
// import etse de İLK evaluate edilen haliyle döner). Bu epikte gerçek bir
// hata olarak bulundu: LocationsPage.test.tsx'te fark edilmeden (assertion'lar
// veriye bağlı değildi) sızmıştı, bu testte (assertion'lar veriye bağlı)
// geocode isteğinin hiç gitmediğini ortaya çıkardı.

vi.mock("../../../hooks/useDebounce", () => ({
  useDebounce: (value: string) => value,
}));

vi.mock("../../ui/Modal", () => ({
  Modal: ({ children, isOpen, title }: any) =>
    isOpen ? (
      <div role="dialog" aria-label={title ?? "location-modal"}>
        {children}
      </div>
    ) : null,
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("LocationFormModal (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let LocationFormModal: typeof import("../LocationFormModal").LocationFormModal;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    authToken = token;
    sessionStorage.setItem("access_token", token);
    ({ render, screen, fireEvent, waitFor } = await import(
      "../../../test/test-utils"
    ));
    ({ LocationFormModal } = await import("../LocationFormModal"));

    // Backend cold-start warm-up: the first real request after process
    // startup lazily loads a RAG/FAISS embedding model (seconds of one-time
    // cost, observed directly in the backend log during this conversion),
    // which made the FIRST geocode round-trip in the test body flaky
    // against a fixed timeout. Absorb that cost here, outside the timed test.
    const axios = (await import("axios")).default;
    await axios
      .get(`${REAL_BACKEND_ORIGIN}/api/v1/locations/geocode`, {
        params: { q: "warmup", limit: 1 },
        headers: { Authorization: `Bearer ${token}` },
      })
      .catch(() => undefined);
  }, 30000);

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("geocodes both addresses and auto-calculates real route details after selection", async () => {
    const user = userEvent.setup();

    render(
      <LocationFormModal
        isOpen
        onClose={vi.fn()}
        onSave={vi.fn()}
        location={null}
      />,
    );

    // NOT: test-utils'in AuthProvider'ı mount'ta initAuth() ile /auth/me
    // çağırıyor; auth-service.ts'in kendi ayrı VITE_API_URL okuması bu
    // testin gerçek backend'iyle URL-konvansiyonu uyuşmuyor (ayrı bir ön
    // koşul sorunu, bu testin kapsamı dışı) — başarısız olunca
    // AuthContext.tsx bizim manuel set ettiğimiz access_token'ı sessizce
    // sessionStorage'dan siliyor. Her gerçek istekten hemen önce token'ı
    // yeniden set ederek bu yan etkiyi etkisiz kılıyoruz.
    const reinjectToken = () =>
      sessionStorage.setItem("access_token", authToken);

    reinjectToken();
    fireEvent.change(screen.getByLabelText(/çıkış yeri arama/i), {
      target: { value: "Hadimkoy Lojistik" },
    });
    reinjectToken();
    await user.click(
      await screen.findByRole(
        "button",
        { name: /Hadimkoy Lojistik/i },
        { timeout: 10000 },
      ),
    );

    reinjectToken();
    fireEvent.change(screen.getByLabelText(/varış yeri arama/i), {
      target: { value: "Ostim Fabrika" },
    });
    reinjectToken();
    await user.click(
      await screen.findByRole(
        "button",
        { name: /Ostim Fabrika/i },
        { timeout: 10000 },
      ),
    );
    reinjectToken();

    // Real route-info round-trip via api_stub's default ORS geojson
    // response (100km, real physics fuel estimate attached server-side).
    await waitFor(
      () => {
        expect(screen.getByLabelText(/mesafe \(km\)/i)).toHaveValue(100);
      },
      { timeout: 10000 },
    );
  }, 30000);
});
