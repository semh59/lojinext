/**
 * 0-mock epiği (AI domain): ChatAssistant.test.tsx bilerek tam mock'lu
 * bırakıldı (bkz. o dosyanın başındaki not) çünkü içindeki "Düşünüyor..."
 * yükleme-durumu testi sonsuza kadar resolve olmayan bir Promise'e dayanıyor
 * — gerçek bir HTTP round-trip bunu asla garanti edemez (backend er ya da
 * geç yanıt döner). Aynı dosyada hem gerçek `../../../api/ai` hem de
 * sonsuz-bekleyen mock'unu barındırmak epik madde 4'teki gerçek çakışma
 * durumu — bu yüzden bu kardeş dosyaya ayrıldı.
 *
 * Burada TEK gerçek-backend senaryosu kapsanıyor: kullanıcı mesaj gönderir
 * → gerçek POST /api/v1/ai/chat round-trip'i tamamlanır → yükleniyor durumu
 * biter → yeni bir asistan balonu render edilir. `aiApi.chat` orval-generated
 * client kullanıyor (customAxiosInstance) → REAL_BACKEND_ORIGIN konvansiyonu.
 *
 * Yanıtın gerçek metnine (Groq LLM çıktısı) BİLEREK bağlanmıyoruz: bu
 * ortamda .env'deki GROQ_API_BASE_URL zaten "/openai/v1" içeriyor ve Groq
 * SDK'sı bunu tekrar ekleyip 404 üretiyor (gerçek, önceden var olan
 * env-config bug'ı — AI domain kapsamı dışı; app/core/services/ai_service.py
 * bu hatayı yutup "Hata: ..." metnini `response` olarak dönüyor, asla
 * raise etmiyor). Bu yüzden sadece round-trip'in tamamlandığını ve
 * karşılık gelen yeni bir asistan mesajının render edildiğini doğruluyoruz,
 * içeriğe bağlanmıyoruz (prod'da veya bu env-bug'ı düzeldiğinde farklı
 * bir LLM çıktısı dönebilir).
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

// jsdom doesn't implement scrollIntoView — patch Element prototype
Object.defineProperty(window.HTMLElement.prototype, "scrollIntoView", {
  configurable: true,
  value: vi.fn(),
});

// framer-motion / sonner: harmless third-party UI libs, keep mocked
// (matches epic rule 4a — not the backend seam under test here).
vi.mock("framer-motion", () => ({
  motion: {
    button: ({ children, onClick, ...rest }: any) => (
      <button onClick={onClick} {...rest}>
        {children}
      </button>
    ),
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));
vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("ChatAssistant (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let ChatAssistant: typeof import("../ChatAssistant").ChatAssistant;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    localStorage.clear(); // gerçek zustand store'un önceki test-run kalıntısıyla açılmaması için
    ({ render, screen, fireEvent, waitFor } = await import(
      "../../../test/test-utils"
    ));
    ({ ChatAssistant } = await import("../ChatAssistant"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("gerçek mesaj gönderimi /ai/chat round-trip'ini tamamlar ve yeni bir asistan balonu render eder", async () => {
    render(<ChatAssistant />);
    sessionStorage.setItem("access_token", authToken); // AuthContext'in olası temizlemesine karşı

    // Chat penceresini gerçekten aç (toggleOpen → gerçek GET /ai/status)
    const toggleContainer = document.querySelector(
      '[class*="fixed bottom-24"]',
    )!;
    const toggleBtn = toggleContainer.querySelector("button")!;
    fireEvent.click(toggleBtn);
    sessionStorage.setItem("access_token", authToken);

    await waitFor(
      () => expect(screen.getByText("LojiNext AI Asistan")).toBeInTheDocument(),
      { timeout: 10000 },
    );

    const input = screen.getByPlaceholderText("LojiNext Asistan'a sor...");
    fireEvent.change(input, {
      target: { value: `Filo durumu nedir? ${Date.now()}` },
    });
    sessionStorage.setItem("access_token", authToken);
    const form = input.closest("form")!;
    fireEvent.submit(form);

    // Karşılaşma mesajı zaten bir "LojiNext AI" etiketiyle render ediliyor;
    // gerçek round-trip tamamlanıp yeni asistan mesajı eklendiğinde bu
    // etiketten en az 2 tane olmalı (karşılama + gerçek yanıt).
    await waitFor(
      () => {
        const bubbles = screen.getAllByText("LojiNext AI");
        expect(bubbles.length).toBeGreaterThanOrEqual(2);
      },
      { timeout: 20000 },
    );
  }, 25000);
});
