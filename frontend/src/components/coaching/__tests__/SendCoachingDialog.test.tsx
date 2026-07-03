/**
 * 0-mock epiği (coaching domain): 3 saf-render senaryosu (null props,
 * textarea preset, disabled buton) hiçbir zaman coachingService'e
 * dokunmuyor — değişiklik yok. "Başarılı gönderim" + "409 kayıtlı değil"
 * senaryoları `SendCoachingDialog.real-backend.test.tsx` dosyasında ele
 * alındı:
 * - 409 senaryosu tamamen gerçek: telegram_id'siz gerçek bir şoför
 *   (seed gerektirmez, API üzerinden oluşturulur) ile gerçek 409 tetiklenir.
 * - "Başarılı gönderim" senaryosu backend'in POST /coaching/{id}/send
 *   endpoint'inin GERÇEK Telegram Bot API'sine (https://api.telegram.org)
 *   canlı bir HTTP isteği attığını okuyunca (app/api/v1/endpoints/
 *   coaching.py:send_coaching, httpx.AsyncClient ile doğrudan
 *   sendMessage çağrısı) risk taşıdığı için DOKÜMANTE mock'lu bırakıldı
 *   (vi.spyOn coachingService.send üzerinde, tek testte, restore
 *   edilerek) — ayrıca sürücü oluşturma endpoint'i (POST /drivers/)
 *   SoforCreate.telegram_id alanını service.add_sofor(...)'a hiç
 *   iletmiyor (app/api/v1/endpoints/drivers.py:126-133), yani public
 *   API'den telegram_id'li bir şoför oluşturmak zaten mümkün değil —
 *   bu ayrı, kapsam dışı bir bulgu (drivers/sofor domain'i, bu dosyanın
 *   sınırları dışında, dokunulmadı).
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/coaching", () => ({
  coachingService: {
    send: vi.fn(),
  },
}));

vi.mock("../../../context/NotificationContext", async () => {
  const actual = await vi.importActual<any>(
    "../../../context/NotificationContext",
  );
  return {
    ...actual,
    useNotify: () => ({ notify: vi.fn() }),
  };
});

import { coachingService } from "../../../api/coaching";
import { SendCoachingDialog } from "../SendCoachingDialog";

const INSIGHT = {
  category: "yakit_yonetimi" as const,
  pattern: "Pattern",
  evidence: ["e1"],
  suggestion: "Rölantide bekleme süresini azaltın.",
  impact_score: 0.4,
};

describe("SendCoachingDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("soforId=null veya insight=null ise hiçbir şey render etmez", () => {
    const { container: c1 } = render(
      <SendCoachingDialog
        soforId={null}
        soforAdi=""
        insight={INSIGHT}
        onClose={vi.fn()}
      />,
    );
    const { container: c2 } = render(
      <SendCoachingDialog
        soforId={7}
        soforAdi="Ali"
        insight={null}
        onClose={vi.fn()}
      />,
    );
    expect(c1.firstChild).toBeNull();
    expect(c2.firstChild).toBeNull();
  });

  it("insight.suggestion textarea preset olur", () => {
    render(
      <SendCoachingDialog
        soforId={7}
        soforAdi="Ali"
        insight={INSIGHT}
        onClose={vi.fn()}
      />,
    );
    const textarea = screen.getByLabelText("Mesaj") as HTMLTextAreaElement;
    expect(textarea.value).toBe(INSIGHT.suggestion);
  });

  it("mesaj <10 karakter ise Gönder butonu disabled", () => {
    render(
      <SendCoachingDialog
        soforId={7}
        soforAdi="Ali"
        insight={{ ...INSIGHT, suggestion: "kısa" }}
        onClose={vi.fn()}
      />,
    );
    const btn = screen.getByRole("button", { name: /Gönder/ });
    expect(btn).toBeDisabled();
  });

  it("başarılı gönderim → onClose çağrılır", async () => {
    (coachingService.send as ReturnType<typeof vi.fn>).mockResolvedValue({
      sent: true,
      delivery_id: null,
      channel: "telegram",
      sent_at: new Date().toISOString(),
    });

    const onClose = vi.fn();
    render(
      <SendCoachingDialog
        soforId={7}
        soforAdi="Ali"
        insight={INSIGHT}
        onClose={onClose}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Gönder/ }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(coachingService.send).toHaveBeenCalledWith(
      7,
      INSIGHT.suggestion,
      "yakit_yonetimi",
    );
  });
});
