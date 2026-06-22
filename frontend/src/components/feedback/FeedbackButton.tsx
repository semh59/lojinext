import { useState } from "react";
import { MessageSquarePlus } from "lucide-react";
import { useLocation } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { sendFeedback } from "@/api/feedback";

type Status = "idle" | "sending" | "sent" | "error";

/**
 * Faz 11 — pilot geri bildirim widget'ı. Sağ-altta sabit buton; modal'da mesaj.
 * Best-effort: gönderim Telegram OPS'a düşer (backend best-effort).
 */
export function FeedbackButton() {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const location = useLocation();

  const close = () => {
    setOpen(false);
    setStatus("idle");
    setMessage("");
  };

  const submit = async () => {
    if (!message.trim()) return;
    setStatus("sending");
    try {
      await sendFeedback({ message: message.trim(), page: location.pathname });
      setStatus("sent");
      setMessage("");
    } catch {
      setStatus("error");
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Geri bildirim gönder"
        className="fixed bottom-5 right-5 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-accent text-white shadow-lg transition hover:scale-105"
      >
        <MessageSquarePlus className="h-5 w-5" />
      </button>

      <Modal isOpen={open} onClose={close} title="Geri Bildirim">
        {status === "sent" ? (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-primary">
              Teşekkürler! Geri bildiriminiz iletildi.
            </p>
            <Button onClick={close}>Kapat</Button>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={4}
              maxLength={2000}
              placeholder="Önerinizi veya karşılaştığınız sorunu yazın…"
              className="w-full rounded-card border border-border bg-elevated px-3 py-2 text-sm text-primary"
            />
            {status === "error" && (
              <p className="text-sm text-red-500">
                Gönderilemedi. Lütfen tekrar deneyin.
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={close}>
                İptal
              </Button>
              <Button
                onClick={submit}
                disabled={status === "sending" || !message.trim()}
              >
                {status === "sending" ? "Gönderiliyor…" : "Gönder"}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}
