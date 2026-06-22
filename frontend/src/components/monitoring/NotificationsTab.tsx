import { AnimatePresence, motion } from "framer-motion";
import { CheckCheck, Bell, BellOff } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/Button";
import { ConnectionStatus } from "./ConnectionStatus";
import { useNotifications } from "./useNotifications";
import { useLocale } from "../../hooks/useLocale";
import type {
  WsNotification,
  ConnectionStatus as WsStatus,
} from "./useMonitoringSocket";

interface Props {
  wsNotifications: WsNotification[];
  wsStatus: WsStatus;
  onReconnect: () => void;
}

const EVENT_BADGE: Record<string, string> = {
  SEFER_UPDATED: "bg-accent/10 text-accent",
  SLA_DELAY: "bg-warning/10 text-warning",
  ANOMALY_DETECTED: "bg-danger/10 text-danger",
  ERROR: "bg-danger/10 text-danger",
  WARNING: "bg-warning/10 text-warning",
  SUCCESS: "bg-success/10 text-success",
  INFO: "bg-accent/10 text-accent",
};

function badgeClass(type: string) {
  return EVENT_BADGE[type?.toUpperCase?.()] ?? "bg-elevated text-secondary";
}

function formatTime(iso: string, locale: string) {
  try {
    return new Date(iso).toLocaleString(locale, {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function NotificationsTab({
  wsNotifications,
  wsStatus,
  onReconnect,
}: Props) {
  const { t } = useTranslation();
  const { notifications, unreadCount, isLoading, markRead, markAllRead } =
    useNotifications(wsNotifications);
  const locale = useLocale();

  return (
    <div className="space-y-4">
      {/* Connection + actions row */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex-1 min-w-0">
          <ConnectionStatus
            status={wsStatus}
            notificationCount={notifications.length}
            onReconnect={onReconnect}
          />
        </div>
        {unreadCount > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => markAllRead.mutate()}
            disabled={markAllRead.isPending}
            className="shrink-0 flex items-center gap-1.5"
          >
            <CheckCheck size={14} />
            {t("monitoring.mark_all_read", { n: unreadCount })}
          </Button>
        )}
      </div>

      {/* Feed */}
      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-16 animate-pulse rounded-card bg-elevated/50"
            />
          ))}
        </div>
      ) : notifications.length === 0 ? (
        <div className="flex h-48 flex-col items-center justify-center gap-2 rounded-modal border border-dashed border-border text-secondary">
          <BellOff size={24} strokeWidth={1.5} />
          <p className="text-sm">{t("monitoring.no_notifications")}</p>
        </div>
      ) : (
        <div className="space-y-2 max-h-[65vh] overflow-y-auto pr-1">
          <AnimatePresence initial={false}>
            {notifications.map((n) => (
              <motion.div
                key={`${n.id}-${n.olusturma_tarihi}`}
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className={`rounded-card border bg-surface px-4 py-3 transition-colors ${
                  n.okundu
                    ? "border-border/40 opacity-60"
                    : "border-border/80 border-l-4 border-l-accent/60"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      {!n.okundu && (
                        <Bell size={11} className="text-accent flex-shrink-0" />
                      )}
                      <span
                        className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider ${badgeClass(
                          n.olay_tipi,
                        )}`}
                      >
                        {n.olay_tipi ||
                          t("monitoring.notification_badge", "NOTIFICATION")}
                      </span>
                      <span className="text-[10px] text-tertiary">
                        {formatTime(n.olusturma_tarihi, locale)}
                      </span>
                    </div>
                    <p className="text-sm font-semibold text-primary leading-snug">
                      {n.baslik}
                    </p>
                    <p className="mt-0.5 text-xs text-secondary">{n.icerik}</p>
                  </div>
                  {!n.okundu && (
                    <button
                      onClick={() => markRead.mutate(n.id)}
                      disabled={markRead.isPending}
                      className="shrink-0 text-[11px] font-semibold text-tertiary hover:text-accent transition-colors mt-0.5"
                    >
                      {t("monitoring.mark_read")}
                    </button>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
