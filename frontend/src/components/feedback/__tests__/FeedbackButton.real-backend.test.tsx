/**
 * 0-mock epiği: FeedbackButton.test.tsx'in mock'lu senaryolarına ek olarak,
 * gerçek backend'e karşı POST /api/v1/feedback/ akışını doğrular.
 *
 * Backend `POST /feedback/` her zaman 202 döner (best-effort Telegram
 * relay — teslimat başarısızlığı yanıtı etkilemez; curl ile doğrulandı).
 * Gerçek bir hata senaryosu üretmek için 2000 karakter validation limitini
 * aşan bir mesaj kullanıyoruz (client-side maxLength=2000 textarea attribute'u
 * ile engellense de, fireEvent.change DOM validasyonunu bypass eder — bu
 * yüzden 422 senaryosu gerçek ağ üzerinden tetiklenebiliyor).
 */
import { describe, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("FeedbackButton (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let FeedbackButton: typeof import("../FeedbackButton").FeedbackButton;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, fireEvent, waitFor } = await import(
      "../../../test/test-utils"
    ));
    ({ FeedbackButton } = await import("../FeedbackButton"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("gerçek backend'e gönderir, 202 alır, teşekkür mesajı gösterir", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<FeedbackButton />);

    fireEvent.click(screen.getByLabelText("Geri bildirim gönder"));
    const textarea = screen.getByPlaceholderText(/Önerinizi/i);
    fireEvent.change(textarea, {
      target: { value: `real-backend test feedback ${Date.now()}` },
    });
    fireEvent.click(screen.getByRole("button", { name: "Gönder" }));

    await waitFor(() => screen.getByText(/Teşekkürler/i), { timeout: 10000 });
  }, 15000);

  it("422 validation hatasında hata mesajı gösterir (2000 karakter limiti aşıldığında)", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<FeedbackButton />);

    fireEvent.click(screen.getByLabelText("Geri bildirim gönder"));
    const textarea = screen.getByPlaceholderText(/Önerinizi/i);
    // fireEvent.change DOM maxLength kısıtını bypass eder — backend'in 2000
    // karakter validation'ını gerçekten tetikler (curl ile 422 doğrulandı).
    fireEvent.change(textarea, { target: { value: "a".repeat(2001) } });
    fireEvent.click(screen.getByRole("button", { name: "Gönder" }));

    await waitFor(() => screen.getByText(/Gönderilemedi/i), {
      timeout: 10000,
    });
  }, 15000);
});
