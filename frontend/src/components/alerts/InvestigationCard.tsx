import { AlertTriangle, User2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "../../lib/utils";
import type { Investigation, SuspicionLevel } from "../../api/investigations";
import { useInvestigationsResources } from "../../resources/useResources";

interface InvestigationCardProps {
  investigation: Investigation;
  onClick: () => void;
}

const LEVEL_STYLE: Record<
  SuspicionLevel,
  { bg: string; text: string; border: string }
> = {
  high: { bg: "bg-danger/10", text: "text-danger", border: "border-danger/30" },
  medium: {
    bg: "bg-warning/10",
    text: "text-warning",
    border: "border-warning/30",
  },
  low: { bg: "bg-elevated", text: "text-secondary", border: "border-border" },
  unknown: {
    bg: "bg-elevated",
    text: "text-tertiary",
    border: "border-border",
  },
};

function useTimeAgo() {
  const { t } = useTranslation();
  return (iso: string): string => {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const diffMs = Date.now() - d.getTime();
    const mins = Math.floor(diffMs / 60_000);
    if (mins < 60)
      return t("alerts.time_mins_ago", "{{n}} min ago", { n: mins });
    const hours = Math.floor(mins / 60);
    if (hours < 24)
      return t("alerts.time_hours_ago", "{{n}} hr ago", { n: hours });
    const days = Math.floor(hours / 24);
    return t("alerts.time_days_ago", "{{n}} day ago", { n: days });
  };
}

export function InvestigationCard({
  investigation,
  onClick,
}: InvestigationCardProps) {
  const { investigationsText } = useInvestigationsResources();
  const formatRelativeShort = useTimeAgo();
  const level = (investigation.suspicion_level ?? "unknown") as SuspicionLevel;
  const style = LEVEL_STYLE[level];
  const sapma = investigation.sapma_yuzde;

  return (
    <button
      type="button"
      onClick={onClick}
      className="group w-full rounded-card border border-border bg-surface p-3 text-left shadow-sm transition-all hover:border-accent/30 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
    >
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider",
            style.bg,
            style.text,
            style.border,
          )}
        >
          {level === "high" && <AlertTriangle className="h-2.5 w-2.5" />}
          {investigationsText.suspicionLabels[level]}
        </span>
        {investigation.suspicion_score != null && (
          <span className="font-mono text-[10px] text-tertiary tabular-nums">
            {investigation.suspicion_score.toFixed(2)}
          </span>
        )}
      </div>

      <p className="text-xs font-bold text-primary truncate">
        {investigation.plaka ?? "—"}
      </p>
      {investigation.sofor_adi && (
        <p className="flex items-center gap-1 text-[10px] text-secondary truncate">
          <User2 className="h-2.5 w-2.5" />
          {investigation.sofor_adi}
        </p>
      )}

      <div className="mt-2 flex items-center justify-between gap-2 text-[10px]">
        {sapma != null ? (
          <span
            className={cn(
              "font-mono tabular-nums font-semibold",
              sapma > 0 ? "text-danger" : "text-success",
            )}
          >
            {sapma > 0 ? "+" : ""}
            {sapma.toFixed(1)}%
          </span>
        ) : (
          <span className="text-tertiary">—</span>
        )}
        <span className="text-tertiary">
          {formatRelativeShort(investigation.created_at)}
        </span>
      </div>
    </button>
  );
}
