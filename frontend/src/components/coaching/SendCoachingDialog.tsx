import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AlertCircle, Loader2, Send, X } from "lucide-react";
import {
  coachingService,
  type CoachingCategory,
  type CoachingInsight,
} from "../../api/coaching";
import { useNotify } from "../../context/NotificationContext";
import { useCoachingResources } from "../../resources/useResources";
import { useTranslation } from "react-i18next";

interface SendCoachingDialogProps {
  soforId: number | null;
  soforAdi: string;
  insight: CoachingInsight | null;
  onClose: () => void;
}

const MIN_LEN = 10;
const MAX_LEN = 1000;

export function SendCoachingDialog({
  soforId,
  soforAdi,
  insight,
  onClose,
}: SendCoachingDialogProps) {
  const { t } = useTranslation();
  const { sendCoachingDialogText } = useCoachingResources();
  const { notify } = useNotify();
  const [message, setMessage] = useState("");

  // Insight değiştikçe message'i preset'le.
  useEffect(() => {
    if (insight) {
      setMessage(insight.suggestion);
    } else {
      setMessage("");
    }
  }, [insight]);

  const sendMutation = useMutation({
    mutationFn: () =>
      coachingService.send(
        soforId!,
        message.trim(),
        insight?.category as CoachingCategory | undefined,
      ),
    onSuccess: () => {
      notify(
        "success",
        sendCoachingDialogText.successTitle,
        sendCoachingDialogText.successMessage,
      );
      onClose();
    },
    onError: (err: any) => {
      const detail =
        err?.response?.data?.error?.message ??
        err?.response?.data?.detail ??
        sendCoachingDialogText.errorMessage;
      // Telegram'a kayıtlı değil özel mesajı
      if (err?.response?.status === 409) {
        notify(
          "warning",
          sendCoachingDialogText.notRegisteredTitle,
          sendCoachingDialogText.notRegisteredMessage,
        );
        return;
      }
      notify("error", sendCoachingDialogText.errorTitle, detail);
    },
  });

  if (soforId === null || insight === null) return null;

  const trimmedLen = message.trim().length;
  const isValid = trimmedLen >= MIN_LEN && trimmedLen <= MAX_LEN;
  const lengthError =
    trimmedLen > 0 && trimmedLen < MIN_LEN
      ? sendCoachingDialogText.minLength
      : trimmedLen > MAX_LEN
        ? sendCoachingDialogText.maxLength
        : null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
      <div className="relative w-full max-w-lg overflow-hidden rounded-modal border border-border bg-surface shadow-2xl">
        <div className="flex items-center justify-between border-b border-border bg-elevated/40 p-4">
          <div>
            <h3 className="text-sm font-semibold text-primary">
              {sendCoachingDialogText.title}
            </h3>
            <p className="text-[11px] text-secondary">
              {sendCoachingDialogText.subtitle(soforAdi)}
            </p>
          </div>
          <button
            onClick={onClose}
            disabled={sendMutation.isPending}
            className="rounded-full p-1.5 text-secondary transition-colors hover:bg-elevated hover:text-primary disabled:opacity-30"
            aria-label={t("common.close")}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-3 p-4">
          <label
            htmlFor="coaching-message"
            className="block text-[11px] font-bold uppercase tracking-wider text-secondary"
          >
            {sendCoachingDialogText.messageLabel}
          </label>
          <textarea
            id="coaching-message"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={5}
            maxLength={MAX_LEN}
            placeholder={sendCoachingDialogText.messagePlaceholder}
            disabled={sendMutation.isPending}
            className="w-full rounded-card border border-border bg-elevated px-3 py-2 text-sm text-primary outline-none focus:border-accent"
          />
          <div className="flex items-center justify-between text-[10px]">
            {lengthError ? (
              <span className="flex items-center gap-1 text-danger">
                <AlertCircle className="h-3 w-3" />
                {lengthError}
              </span>
            ) : (
              <span className="text-tertiary">
                {trimmedLen}/{MAX_LEN}
              </span>
            )}
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={onClose}
              disabled={sendMutation.isPending}
              className="rounded-card px-3 py-1.5 text-xs font-semibold text-secondary transition-colors hover:bg-elevated hover:text-primary disabled:opacity-50"
            >
              {sendCoachingDialogText.cancel}
            </button>
            <button
              onClick={() => sendMutation.mutate()}
              disabled={!isValid || sendMutation.isPending}
              className="inline-flex items-center gap-2 rounded-card bg-accent px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-accent/90 disabled:opacity-50"
            >
              {sendMutation.isPending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Send className="h-3 w-3" />
              )}
              {sendCoachingDialogText.sendButton}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
