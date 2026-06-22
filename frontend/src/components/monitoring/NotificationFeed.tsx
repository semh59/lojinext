import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { WsNotification } from "./useMonitoringSocket";

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString("tr-TR");
  } catch {
    return iso;
  }
}

interface EventConfig {
  border: string;
  badge: string;
  dot: string;
}

const EVENT_CONFIG: Record<string, EventConfig> = {
  ERROR: {
    border: "border-l-danger/60",
    badge: "bg-danger/10 text-danger",
    dot: "bg-danger",
  },
  CRITICAL: {
    border: "border-l-danger/60",
    badge: "bg-danger/10 text-danger",
    dot: "bg-danger",
  },
  WARNING: {
    border: "border-l-warning/60",
    badge: "bg-warning/10 text-warning",
    dot: "bg-warning",
  },
  SUCCESS: {
    border: "border-l-success/60",
    badge: "bg-success/10 text-success",
    dot: "bg-success",
  },
  INFO: {
    border: "border-l-accent/60",
    badge: "bg-accent/10 text-accent",
    dot: "bg-accent",
  },
};

function getEventConfig(type: string): EventConfig {
  return (
    EVENT_CONFIG[type.toUpperCase()] ?? {
      border: "border-l-border",
      badge: "bg-elevated text-secondary",
      dot: "bg-secondary",
    }
  );
}

export function NotificationFeed({
  notifications,
}: {
  notifications: WsNotification[];
}) {
  const [activeFilter, setActiveFilter] = useState<string | null>(null);

  if (notifications.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-modal border border-dashed border-border text-sm text-secondary">
        Henüz bildirim yok
      </div>
    );
  }

  // Unique event types present in the feed
  const types = Array.from(
    new Set(notifications.map((n) => n.olay_tipi.toUpperCase())),
  );
  const filtered = activeFilter
    ? notifications.filter((n) => n.olay_tipi.toUpperCase() === activeFilter)
    : notifications;

  return (
    <div className="space-y-3">
      {/* Filter bar */}
      {types.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setActiveFilter(null)}
            className={`px-2.5 py-1 rounded-full text-[11px] font-bold transition-colors ${
              activeFilter === null
                ? "bg-accent text-white"
                : "bg-elevated text-secondary hover:text-primary"
            }`}
          >
            Tümü ({notifications.length})
          </button>
          {types.map((type) => {
            const cfg = getEventConfig(type);
            const count = notifications.filter(
              (n) => n.olay_tipi.toUpperCase() === type,
            ).length;
            return (
              <button
                key={type}
                onClick={() =>
                  setActiveFilter(activeFilter === type ? null : type)
                }
                className={`px-2.5 py-1 rounded-full text-[11px] font-bold transition-colors ${
                  activeFilter === type
                    ? cfg.badge + " ring-1 ring-current/40"
                    : "bg-elevated text-secondary hover:text-primary"
                }`}
              >
                {type} ({count})
              </button>
            );
          })}
        </div>
      )}

      {/* Feed */}
      <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
        <AnimatePresence initial={false}>
          {filtered.map((n) => {
            const cfg = getEventConfig(n.olay_tipi);
            return (
              <motion.div
                key={`${n.id}-${n.olusturma_tarihi}`}
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className={`rounded-card border border-l-4 border-border/60 bg-surface px-4 py-3 ${cfg.border}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider ${cfg.badge}`}
                      >
                        {n.olay_tipi}
                      </span>
                    </div>
                    <p className="mt-1 text-sm font-semibold text-primary">
                      {n.baslik}
                    </p>
                    <p className="mt-0.5 text-xs text-secondary">{n.icerik}</p>
                  </div>
                  <span className="shrink-0 text-[10px] text-tertiary pt-0.5">
                    {formatTime(n.olusturma_tarihi)}
                  </span>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
