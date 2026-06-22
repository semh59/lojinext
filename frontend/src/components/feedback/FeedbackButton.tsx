import { useState } from "react";
import { MessageSquarePlus } from "lucide-react";
import { useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { sendFeedback } from "@/api/feedback";

type Status = "idle" | "sending" | "sent" | "error";

export function FeedbackButton() {
  const { t } = useTranslation();
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
        aria-label={t("feedback.aria_label")}
        className="fixed bottom-5 right-5 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-accent text-white shadow-lg transition hover:scale-105"
      >
        <MessageSquarePlus className="h-5 w-5" />
      </button>

      <Modal isOpen={open} onClose={close} title={t("feedback.send")}>
        {status === "sent" ? (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-primary">{t("feedback.success")}</p>
            <Button onClick={close}>{t("common.close")}</Button>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={4}
              maxLength={2000}
              placeholder={t("feedback.placeholder")}
              className="w-full rounded-card border border-border bg-elevated px-3 py-2 text-sm text-primary"
            />
            {status === "error" && (
              <p className="text-sm text-red-500">{t("feedback.error")}</p>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={close}>
                {t("common.cancel")}
              </Button>
              <Button
                onClick={submit}
                disabled={status === "sending" || !message.trim()}
              >
                {status === "sending"
                  ? t("feedback.sending")
                  : t("feedback.send")}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}
