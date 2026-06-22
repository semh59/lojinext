import { useNavigate } from "react-router-dom";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Bell,
  Clock,
  Route as RouteIcon,
  ShieldAlert,
  Wrench,
} from "lucide-react";

import { cn, safeHref } from "@/lib/utils";
import type { TriageCategory, TriageItem, TriageSeverity } from "@/api/today";
import { useTodayResources } from "@/resources/useResources";
import { useTranslation } from "react-i18next";

const SEVERITY_STYLE: Record<TriageSeverity, string> = {
  critical: "border-l-danger bg-danger/5",
  high: "border-l-warning bg-warning/5",
  medium: "border-l-info bg-info/5",
  low: "border-l-success bg-success/5",
};

const SEVERITY_BADGE: Record<TriageSeverity, string> = {
  critical: "bg-danger/10 text-danger border-danger/30",
  high: "bg-warning/10 text-warning border-warning/30",
  medium: "bg-info/10 text-info border-info/30",
  low: "bg-success/10 text-success border-success/30",
};

const CATEGORY_ICON: Record<TriageCategory, typeof AlertCircle> = {
  anomaly: AlertCircle,
  maintenance: Wrench,
  investigation: ShieldAlert,
  telegram_approval: Bell,
  active_trip: RouteIcon,
};

function useTimeAgo() {
  const { t } = useTranslation();
  return (iso: string): string => {
    const d = new Date(iso);
    const diffMs = Date.now() - d.getTime();
    const mins = Math.floor(diffMs / 60_000);
    if (mins < 1) return t("alerts.time_just_now", "just now");
    if (mins < 60)
      return t("alerts.time_mins_ago", "{{n}} min ago", { n: mins });
    const hours = Math.floor(mins / 60);
    if (hours < 24)
      return t("alerts.time_hours_ago", "{{n}} hr ago", { n: hours });
    const days = Math.floor(hours / 24);
    return t("alerts.time_days_ago", "{{n}} day ago", { n: days });
  };
}

interface Props {
  item: TriageItem;
}

export function TriageItemCard({ item }: Props) {
  const { todayText } = useTodayResources();
  const timeAgo = useTimeAgo();
  const navigate = useNavigate();
  const Icon = CATEGORY_ICON[item.category] ?? AlertCircle;

  const handleAction = (url: string, actionType: string) => {
    if (actionType === "external") {
      const safe = safeHref(url);
      if (safe) window.open(safe, "_blank", "noopener,noreferrer");
    } else if (actionType === "modal") {
      // Modal logic v2.1; v1'de navigate fallback
      navigate(url);
    } else {
      navigate(url);
    }
  };

  return (
    <div
      className={cn(
        "rounded-modal border border-l-4 border-border bg-surface p-4 shadow-sm transition-all hover:shadow-md",
        SEVERITY_STYLE[item.severity],
      )}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="flex items-start gap-2">
          <Icon
            className={cn(
              "mt-0.5 h-4 w-4 shrink-0",
              item.severity === "critical"
                ? "text-danger"
                : item.severity === "high"
                  ? "text-warning"
                  : "text-secondary",
            )}
          />
          <div>
            <p className="text-sm font-semibold text-primary">{item.title}</p>
            {item.subtitle && (
              <p className="mt-0.5 text-[11px] text-secondary">
                {item.subtitle}
              </p>
            )}
          </div>
        </div>
        <span
          className={cn(
            "inline-block rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider",
            SEVERITY_BADGE[item.severity],
          )}
        >
          {todayText.severity[item.severity]}
        </span>
      </div>

      <div className="flex items-center justify-between gap-2 pt-2">
        <div className="flex items-center gap-2 text-[10px] text-tertiary">
          {item.plaka && (
            <span className="font-mono font-semibold text-primary">
              {item.plaka}
            </span>
          )}
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {timeAgo(item.timestamp)}
          </span>
        </div>
        {item.actions.length > 0 && (
          <div className="flex gap-1.5">
            {item.actions.map((a, i) => (
              <button
                key={i}
                type="button"
                onClick={() => handleAction(a.url, a.action_type)}
                className={cn(
                  "inline-flex items-center gap-1 rounded-card px-2.5 py-1 text-xs font-semibold transition-all",
                  i === 0
                    ? "bg-accent text-white shadow-sm hover:bg-accent/90"
                    : "border border-border bg-elevated text-secondary hover:bg-elevated/70",
                )}
              >
                {a.label}
                {i === 0 && <ArrowRight className="h-3 w-3" />}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export { AlertTriangle };
