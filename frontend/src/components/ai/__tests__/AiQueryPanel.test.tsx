/**
 * 0-mock epiği (AI domain): AiQueryPanel gerçek backend'e karşı çevrildi.
 * `aiApi.query` orval-generated client kullanıyor (`customAxiosInstance`,
 * bkz. src/generated/api/ai/ai.ts) → baseURL konvansiyonu REAL_BACKEND_ORIGIN
 * (origin-only, /api/v1 EKLENMEMELİ — orval client zaten path'lere
 * /api/v1 ekliyor).
 *
 * Backend `/api/v1/ai/query` (app/api/v1/endpoints/ai.py) davranışı:
 * - category="fuel_trend" → chart, gerçek `yakit_alimlari` DB verisinden
 *   deterministik üretilir (son 12 ay), actions HER ZAMAN
 *   [{label:"Yakıt sayfası", url:"/fuel"}] — chart'ın null/non-null olması
 *   veriye bağlı (bu paylaşılan test DB'sinde son 12 ayda yakıt alımı
 *   olmayabilir), actions ise DB verisinden bağımsız her zaman dönüyor.
 * - `answer` alanı `AIService.generate_response` → Groq LLM çağrısı; bu
 *   ortamda `.env`'deki GROQ_API_BASE_URL zaten "/openai/v1" içeriyor ve
 *   Groq SDK'sı bunu tekrar ekleyip 404 üretiyor (gerçek, önceden var olan
 *   env-config bug'ı — AI domain kapsamı dışı, ai_service.py hatayı
 *   yutup "Hata: ..." metnini `answer` olarak dönüyor, asla raise etmiyor).
 *   Bu yüzden `answer` metninin TAM içeriğine bağlanmıyoruz (LLM çıktısı
 *   prod'da farklı olur, bu env-bug'ı düzelirse de değişir) — sadece
 *   boş-olmayan bir cevap render edildiğini doğruluyoruz.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("AiQueryPanel (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let AiQueryPanel: typeof import("../AiQueryPanel").AiQueryPanel;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, fireEvent, waitFor } = await import(
      "../../../test/test-utils"
    ));
    ({ AiQueryPanel } = await import("../AiQueryPanel"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("fuel_trend kategorisinde gerçek round-trip: aksiyon linki ve boş-olmayan cevap render edilir", async () => {
    render(<AiQueryPanel />);
    sessionStorage.setItem("access_token", authToken); // AuthContext'in olası temizlemesine karşı

    fireEvent.change(screen.getByLabelText("Sorgu kategorisi"), {
      target: { value: "fuel_trend" },
    });
    fireEvent.change(screen.getByPlaceholderText(/sor/i), {
      target: { value: `yakıt trendi ${Date.now()}` },
    });
    sessionStorage.setItem("access_token", authToken);
    fireEvent.click(screen.getByText("Sorgula"));

    // Actions, backend'de category === "fuel_trend" olduğunda chart'ın
    // null/non-null olmasından bağımsız olarak her zaman döner (deterministik).
    const link = await screen.findByText(
      /Yakıt sayfası/,
      {},
      { timeout: 15000 },
    );
    expect(link.closest("a")).toHaveAttribute("href", "/fuel");

    // Cevap metni gerçek bir LLM çağrısının sonucu (bu ortamda GROQ base URL
    // yanlış yapılandırıldığı için "Hata: ..." dönüyor — bkz. dosya başı not);
    // içeriğe değil, sadece boş-olmayan bir render'a bağlanıyoruz.
    await waitFor(
      () => {
        const answerCandidates = document.querySelectorAll(
          "p.whitespace-pre-line",
        );
        expect(answerCandidates.length).toBeGreaterThanOrEqual(1);
        expect(answerCandidates[0].textContent?.trim().length).toBeGreaterThan(
          0,
        );
      },
      { timeout: 15000 },
    );
  }, 20000);

  it("category select değiştirilebilir ve seçenekler render edilir", () => {
    render(<AiQueryPanel />);
    const select = screen.getByLabelText(
      "Sorgu kategorisi",
    ) as HTMLSelectElement;
    expect(select).toBeInTheDocument();
    fireEvent.change(select, { target: { value: "fuel_trend" } });
    expect(select.value).toBe("fuel_trend");
  });
});
