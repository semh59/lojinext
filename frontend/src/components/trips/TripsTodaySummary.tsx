import { useQuery } from "@tanstack/react-query";
import {
  CalendarDays,
  CheckCircle2,
  Loader2,
  MapPin,
  Pause,
  X,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { tripService } from "../../api/trips";
import { getTripStatusMeta } from "../../lib/status-labels";
import { useLocale } from "../../hooks/useLocale";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function TripsTodaySummary() {
  const { t } = useTranslation();
  const locale = useLocale();
  const today = todayIso();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["trips", "stats", "today", today],
    queryFn: () =>
      tripService.getStats({ baslangic_tarih: today, bitis_tarih: today }),
    staleTime: 60 * 1000,
    refetchOnWindowFocus: true,
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-3 rounded-modal border border-border bg-elevated/30 px-5 py-3">
        <Loader2 className="h-4 w-4 animate-spin text-secondary" />
        <span className="text-sm text-secondary">
          {t("dashboard.todays_summary_loading", "Loading today's summary…")}
        </span>
      </div>
    );
  }

  if (isError || !data) {
    return null;
  }

  const total = data.total_count ?? 0;
  if (total === 0) {
    return (
      <div className="flex items-center gap-3 rounded-modal border border-border/60 bg-surface/60 px-5 py-3">
        <CalendarDays className="h-5 w-5 text-secondary" />
        <p className="text-sm text-secondary">
          {t("dashboard.todays_summary_empty", "No trips recorded for today.")}
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-modal border border-accent/20 bg-gradient-to-r from-accent/5 to-info/5 px-5 py-3">
      <div className="flex items-center gap-3">
        <CalendarDays className="h-5 w-5 text-accent" />
        <p className="text-sm font-semibold text-primary">
          <span className="font-mono">{total}</span>{" "}
          {t("dashboard.todays_summary_count", "trips today")}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <Chip
          icon={MapPin}
          label={t("dashboard.in_progress", "En Route")}
          count={data.in_progress_count ?? 0}
          accent="text-warning"
          bg="bg-warning/10"
        />
        <Chip
          icon={CheckCircle2}
          label={getTripStatusMeta("Completed", locale).label}
          count={data.completed_count ?? 0}
          accent="text-success"
          bg="bg-success/10"
        />
        <Chip
          icon={Pause}
          label={getTripStatusMeta("Planned", locale).label}
          count={data.planned_count ?? 0}
          accent="text-info"
          bg="bg-info/10"
        />
        {(data.cancelled_count ?? 0) > 0 && (
          <Chip
            icon={X}
            label={getTripStatusMeta("Cancelled", locale).label}
            count={data.cancelled_count}
            accent="text-danger"
            bg="bg-danger/10"
          />
        )}
      </div>
    </div>
  );
}

function Chip({
  icon: Icon,
  label,
  count,
  accent,
  bg,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  count: number;
  accent: string;
  bg: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-card px-2.5 py-1 font-medium ${bg} ${accent}`}
    >
      <Icon className="h-3.5 w-3.5" />
      <span className="text-secondary">{label}:</span>
      <span className="font-mono font-semibold">{count}</span>
    </span>
  );
}
