import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/coaching", () => ({
  coachingService: {
    getInsights: vi.fn(),
  },
}));

import { coachingService } from "../../../api/coaching";
import { CoachingInsightsPanel } from "../CoachingInsightsPanel";

describe("CoachingInsightsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('soforId=null → "şoför seçin" mesajı, query çalışmaz', () => {
    render(<CoachingInsightsPanel soforId={null} />);
    expect(
      screen.getByText("Detay görmek için sol panelden bir şoför seçin."),
    ).toBeInTheDocument();
    expect(coachingService.getInsights).not.toHaveBeenCalled();
  });

  it('insights boşsa "aktif öneri yok" mesajı', async () => {
    (coachingService.getInsights as ReturnType<typeof vi.fn>).mockResolvedValue(
      {
        sofor_id: 7,
        ad_soyad: "Ali Veli",
        headline: "Şu an için kritik durum yok",
        priority: "low",
        insights: [],
        generated_at: new Date().toISOString(),
        source: "fallback",
      },
    );
    render(<CoachingInsightsPanel soforId={7} />);
    await waitFor(() =>
      expect(screen.getByText("Ali Veli")).toBeInTheDocument(),
    );
    expect(
      screen.getByText("Bu şoför için aktif öneri yok"),
    ).toBeInTheDocument();
    // Kaynak göstergesi
    expect(screen.getByText(/Kural tabanlı/)).toBeInTheDocument();
  });

  it("insight kartı + Telegram gönder butonu render edilir", async () => {
    (coachingService.getInsights as ReturnType<typeof vi.fn>).mockResolvedValue(
      {
        sofor_id: 7,
        ad_soyad: "Ali Veli",
        headline: "Skor 1.13 — 1 alanda iyileştirme",
        priority: "medium",
        insights: [
          {
            category: "yakit_yonetimi",
            pattern: "3 adet anomali, ort %18 sapma",
            evidence: ["3 olay", "ort %18"],
            suggestion: "Rölantide bekleme süresini azaltın",
            impact_score: 0.36,
          },
        ],
        generated_at: new Date().toISOString(),
        source: "llm",
      },
    );

    const onSendClick = vi.fn();
    render(<CoachingInsightsPanel soforId={7} onSendClick={onSendClick} />);

    await waitFor(() =>
      expect(screen.getByText("Ali Veli")).toBeInTheDocument(),
    );
    expect(screen.getByText("Yakıt Yönetimi")).toBeInTheDocument();
    expect(screen.getByText(/3 adet anomali/)).toBeInTheDocument();
    // Evidence chip
    expect(screen.getByText("3 olay")).toBeInTheDocument();
    // Gönder butonu
    const sendBtn = screen.getByRole("button", { name: /Telegram'a gönder/ });
    sendBtn.click();
    expect(onSendClick).toHaveBeenCalledTimes(1);
  });

  it("istek hatası → kırmızı banner", async () => {
    (coachingService.getInsights as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("boom"),
    );
    render(<CoachingInsightsPanel soforId={7} />);
    await waitFor(() =>
      expect(screen.getByText("Öneriler yüklenemedi")).toBeInTheDocument(),
    );
  });

  it("priority=high → kırmızı/danger badge gösterilir", async () => {
    (coachingService.getInsights as ReturnType<typeof vi.fn>).mockResolvedValue(
      {
        sofor_id: 9,
        ad_soyad: "X Y",
        headline: "h",
        priority: "high",
        insights: [],
        generated_at: new Date().toISOString(),
        source: "llm",
      },
    );
    render(<CoachingInsightsPanel soforId={9} />);
    await waitFor(() =>
      expect(screen.getByText(/Yüksek öncelik/)).toBeInTheDocument(),
    );
  });
});
