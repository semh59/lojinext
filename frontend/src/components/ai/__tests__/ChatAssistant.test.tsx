/**
 * 0-mock epiği (AI domain): bu dosya BİLEREK tam mock'lu kalıyor.
 * ChatAssistant testlerinin büyük çoğunluğu backend'e hiç dokunmuyor — sadece
 * `useAiStore`'un (zustand) döndürdüğü isOpen/status/messages'a göre UI'ın
 * doğru render edildiğini doğruluyorlar (store tamamen mock'lu, gerçek HTTP
 * hiç tetiklenmiyor). Bunları gerçek backend'e çevirmek gereksiz risk/yavaşlık
 * katardı, gerçek bir dış sınır test etmiyorlar.
 *
 * Tek gerçek dış-sınır etkileşimi `aiApi.chat` — bunun için 2 test var:
 *  - "submitting form calls aiApi.chat and addMessage": gerçek round-trip'e
 *    çevrilebilir bir deterministik senaryo → GERÇEK backend'e çevrilip
 *    kardeş dosyaya taşındı: `ChatAssistant.real-backend.test.tsx`.
 *  - "shows Düşünüyor... while AI is responding": sonsuza kadar resolve
 *    olmayan bir Promise'e dayanıyor — gerçek bir backend round-trip'i asla
 *    "sonsuza kadar" beklemeyi garanti edemez (backend er ya da geç yanıt
 *    döner), bu yüzden BİLEREK mock'lu kalıyor (epik madde 4'teki "gerçek
 *    çakışma" durumu — aynı dosyada hem gerçek hem sonsuz-mock aynı modül
 *    için olamaz).
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import { ChatAssistant } from "../ChatAssistant";

// jsdom doesn't implement scrollIntoView — patch Element prototype
Object.defineProperty(window.HTMLElement.prototype, "scrollIntoView", {
  configurable: true,
  value: vi.fn(),
});

// framer-motion passthrough
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

// sonner toast
vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

// ai-service
vi.mock("../../../api/ai", () => ({
  aiApi: {
    chat: vi.fn(),
    getStatus: vi
      .fn()
      .mockResolvedValue({ is_ready: true, progress: { status: "ready" } }),
  },
}));

// Zustand ai-store — control open/closed state
const mockToggleOpen = vi.fn();
const mockToggleExpanded = vi.fn();
const mockClearHistory = vi.fn();
const mockAddMessage = vi.fn();
const mockCheckStatus = vi.fn().mockResolvedValue(undefined);

const createStoreMock = (overrides: Record<string, unknown> = {}) => ({
  isOpen: false,
  toggleOpen: mockToggleOpen,
  isExpanded: false,
  toggleExpanded: mockToggleExpanded,
  messages: [
    {
      role: "assistant",
      content:
        "Merhaba! Ben LojiNext Asistan. Filo verileriniz, yakıt tüketimi veya operasyonel analizler hakkında size nasıl yardımcı olabilirim?",
    },
  ],
  addMessage: mockAddMessage,
  clearHistory: mockClearHistory,
  status: "ready" as const,
  checkStatus: mockCheckStatus,
  ...overrides,
});

vi.mock("../../../stores/use-ai-store", () => ({
  useAiStore: vi.fn(() => createStoreMock()),
}));

describe("ChatAssistant", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the toggle button when chat is closed", () => {
    render(<ChatAssistant />);
    // Toggle button is a motion.button wrapping Sparkles icon
    // The button is there but not labeled — find by its container
    const container = document.querySelector('[class*="fixed bottom-24"]');
    expect(container).not.toBeNull();
  });

  it("does not show chat window when isOpen is false", () => {
    render(<ChatAssistant />);
    expect(screen.queryByText("LojiNext AI Asistan")).not.toBeInTheDocument();
  });

  it("shows chat window when isOpen is true", async () => {
    const { useAiStore } = await import("../../../stores/use-ai-store");
    vi.mocked(useAiStore).mockReturnValue(
      createStoreMock({ isOpen: true }) as any,
    );
    render(<ChatAssistant />);
    expect(screen.getByText("LojiNext AI Asistan")).toBeInTheDocument();
  });

  it("shows Hazır status when status is ready", async () => {
    const { useAiStore } = await import("../../../stores/use-ai-store");
    vi.mocked(useAiStore).mockReturnValue(
      createStoreMock({ isOpen: true, status: "ready" }) as any,
    );
    render(<ChatAssistant />);
    expect(screen.getByText("Hazır")).toBeInTheDocument();
  });

  it("shows Hazırlanıyor... when status is loading", async () => {
    const { useAiStore } = await import("../../../stores/use-ai-store");
    vi.mocked(useAiStore).mockReturnValue(
      createStoreMock({ isOpen: true, status: "loading" }) as any,
    );
    render(<ChatAssistant />);
    expect(screen.getByText("Hazırlanıyor...")).toBeInTheDocument();
  });

  it("shows Hata status when status is error", async () => {
    const { useAiStore } = await import("../../../stores/use-ai-store");
    vi.mocked(useAiStore).mockReturnValue(
      createStoreMock({ isOpen: true, status: "error" }) as any,
    );
    render(<ChatAssistant />);
    expect(screen.getByText("Hata")).toBeInTheDocument();
  });

  it("shows Bağlanıyor... when status is offline", async () => {
    const { useAiStore } = await import("../../../stores/use-ai-store");
    vi.mocked(useAiStore).mockReturnValue(
      createStoreMock({ isOpen: true, status: "offline" }) as any,
    );
    render(<ChatAssistant />);
    expect(screen.getByText("Bağlanıyor...")).toBeInTheDocument();
  });

  it("shows suggestion chips when messages is just the initial message", async () => {
    const { useAiStore } = await import("../../../stores/use-ai-store");
    vi.mocked(useAiStore).mockReturnValue(
      createStoreMock({ isOpen: true, messages: [] }) as any,
    );
    render(<ChatAssistant />);
    expect(
      screen.getByText("Tüm filonun sağlık durumu nedir?"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("En verimli güzergah hangisi?"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Bakım zamanı yaklaşanlar kimler?"),
    ).toBeInTheDocument();
  });

  it("renders the assistant initial message", async () => {
    const { useAiStore } = await import("../../../stores/use-ai-store");
    vi.mocked(useAiStore).mockReturnValue(
      createStoreMock({ isOpen: true }) as any,
    );
    render(<ChatAssistant />);
    expect(
      screen.getByText(
        "Merhaba! Ben LojiNext Asistan. Filo verileriniz, yakıt tüketimi veya operasyonel analizler hakkında size nasıl yardımcı olabilirim?",
      ),
    ).toBeInTheDocument();
  });

  it("renders the message input placeholder", async () => {
    const { useAiStore } = await import("../../../stores/use-ai-store");
    vi.mocked(useAiStore).mockReturnValue(
      createStoreMock({ isOpen: true }) as any,
    );
    render(<ChatAssistant />);
    expect(
      screen.getByPlaceholderText("LojiNext Asistan'a sor..."),
    ).toBeInTheDocument();
  });

  it("calls toggleOpen when X button is clicked", async () => {
    const { useAiStore } = await import("../../../stores/use-ai-store");
    vi.mocked(useAiStore).mockReturnValue(
      createStoreMock({ isOpen: true }) as any,
    );
    render(<ChatAssistant />);
    // The chat window is open — find all buttons, click the one that triggers toggleOpen.
    // The X button is the last of the 3 icon buttons in the header flex row.
    // All buttons share similar classes; grab all and click the last icon-only button.
    const allBtns = Array.from(document.querySelectorAll("button"));
    // The close (X) button is identified by having `hover:text-primary` class
    // and being after the expand button. Use: click each until mockToggleOpen is called.
    // Simpler: find the button containing the X SVG icon — it's the only one right
    // after the expand/minimize button in the header.
    const headerIconBtns = allBtns.filter(
      (b) =>
        b.className.includes("hover:bg-elevated") &&
        b.className.includes("rounded-xl") &&
        b.className.includes("text-secondary"),
    );
    // Last one in the header = close button
    fireEvent.click(headerIconBtns[headerIconBtns.length - 1]);
    expect(mockToggleOpen).toHaveBeenCalledTimes(1);
  });

  it("calls clearHistory when trash button is clicked", async () => {
    const { useAiStore } = await import("../../../stores/use-ai-store");
    vi.mocked(useAiStore).mockReturnValue(
      createStoreMock({ isOpen: true }) as any,
    );
    render(<ChatAssistant />);
    const trashBtn = screen.getByTitle("Sohbeti Temizle");
    fireEvent.click(trashBtn);
    expect(mockClearHistory).toHaveBeenCalledTimes(1);
  });

  it("send button is disabled when input is empty", async () => {
    const { useAiStore } = await import("../../../stores/use-ai-store");
    vi.mocked(useAiStore).mockReturnValue(
      createStoreMock({ isOpen: true }) as any,
    );
    render(<ChatAssistant />);
    const submitBtns = document.querySelectorAll('button[type="submit"]');
    expect(submitBtns.length).toBeGreaterThanOrEqual(1);
    expect((submitBtns[0] as HTMLButtonElement).disabled).toBe(true);
  });

  it("typing in input enables send button", async () => {
    const { useAiStore } = await import("../../../stores/use-ai-store");
    vi.mocked(useAiStore).mockReturnValue(
      createStoreMock({ isOpen: true }) as any,
    );
    render(<ChatAssistant />);
    const input = screen.getByPlaceholderText("LojiNext Asistan'a sor...");
    fireEvent.change(input, { target: { value: "Test mesajı" } });
    const submitBtns = document.querySelectorAll('button[type="submit"]');
    expect((submitBtns[0] as HTMLButtonElement).disabled).toBe(false);
  });

  it("clicking suggestion chip sets input value", async () => {
    const { useAiStore } = await import("../../../stores/use-ai-store");
    vi.mocked(useAiStore).mockReturnValue(
      createStoreMock({ isOpen: true, messages: [] }) as any,
    );
    render(<ChatAssistant />);
    fireEvent.click(screen.getByText("En verimli güzergah hangisi?"));
    const input = screen.getByPlaceholderText(
      "LojiNext Asistan'a sor...",
    ) as HTMLInputElement;
    expect(input.value).toBe("En verimli güzergah hangisi?");
  });

  it("2026-07-01 prod-grade denetimi P2 (Dalga 4 madde 25): isOpen persist edilip true olarak geri geldiğinde (panel zaten açık mount oluyor) checkStatus hemen çağrılır — 5sn polling interval'ını beklemez", async () => {
    vi.useFakeTimers();
    try {
      const { useAiStore } = await import("../../../stores/use-ai-store");
      // Persisted state senaryosu: mount anında isOpen=true, status henüz
      // 'ready' değil (offline/loading) — tıpkı sayfa reload sonrası
      // zustand persist'in isOpen'ı geri yüklediği ama status'un
      // persist edilmediği (her zaman 'offline'dan başladığı) durum gibi.
      vi.mocked(useAiStore).mockReturnValue(
        createStoreMock({ isOpen: true, status: "offline" }) as any,
      );
      render(<ChatAssistant />);
      // Sahte zamanlayıcıları ilerletmeden (interval henüz tetiklenmeden)
      // checkStatus zaten en az bir kez çağrılmış olmalı.
      expect(mockCheckStatus).toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("shows Düşünüyor... while AI is responding", async () => {
    const { useAiStore } = await import("../../../stores/use-ai-store");
    const { aiApi } = await import("../../../api/ai");
    // Never resolves — keeps loading state
    (aiApi.chat as ReturnType<typeof vi.fn>).mockReturnValue(
      new Promise(() => {}),
    );
    vi.mocked(useAiStore).mockReturnValue(
      createStoreMock({ isOpen: true }) as any,
    );
    render(<ChatAssistant />);
    const input = screen.getByPlaceholderText("LojiNext Asistan'a sor...");
    fireEvent.change(input, { target: { value: "Test soru" } });
    const form = input.closest("form")!;
    fireEvent.submit(form);
    await waitFor(() => {
      expect(screen.getByText("Düşünüyor...")).toBeInTheDocument();
    });
  });
});
