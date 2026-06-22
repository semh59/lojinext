import {
  AlertCircle,
  Info,
  Loader2,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { useFvi } from "@/hooks/useExecutive";
import { useExecutiveResources } from "@/resources/useResources";

interface Props {
  className?: string;
}

function SubScoreBar({ label, value }: { label: string; value: number }) {
  const pct = Math.max(0, Math.min(100, value));
  const tone =
    pct >= 75 ? "bg-success" : pct >= 50 ? "bg-warning" : "bg-danger/70";
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-[11px]">
        <span className="text-secondary">{label}</span>
        <span className="font-mono font-semibold text-primary">
          {value.toFixed(0)}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-elevated">
        <div
          className={cn("h-full transition-all", tone)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function FleetEfficiencyCard({ className }: Props) {
  const { executiveText } = useExecutiveResources();
  const { data, isLoading, error } = useFvi();
  const t = executiveText.fvi;

  if (isLoading) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 rounded-modal border border-border bg-surface p-6 shadow-sm",
          className,
        )}
      >
        <Loader2 className="h-4 w-4 animate-spin text-secondary" />
        <span className="text-sm text-secondary">{t.title}…</span>
      </div>
    );
  }

  if (error || !data) {
    const status = (error as { response?: { status?: number } })?.response
      ?.status;
    const msg =
      status === 503
        ? executiveText.errors.flagOff
        : status === 403
          ? executiveText.errors.forbidden
          : executiveText.errors.loadFailed;
    return (
      <div
        className={cn(
          "flex items-start gap-2 rounded-modal border border-danger/30 bg-danger/5 p-4 text-sm text-danger",
          className,
        )}
      >
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
        {msg}
      </div>
    );
  }

  const trend = data.trend_30d;
  const TrendIcon = trend && trend > 0 ? TrendingUp : TrendingDown;
  const trendColor =
    trend === null || trend === undefined
      ? "text-tertiary"
      : trend > 0
        ? "text-success"
        : trend < 0
          ? "text-danger"
          : "text-secondary";

  return (
    <div
      className={cn(
        "rounded-modal border border-border bg-surface p-6 shadow-sm",
        className,
      )}
    >
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h3 className="text-xs font-bold uppercase tracking-widest text-secondary">
            {t.title}
          </h3>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="font-mono text-4xl font-bold text-accent">
              {data.fvi.toFixed(0)}
            </span>
            <span className="text-xs text-tertiary">{t.outOf}</span>
          </div>
        </div>
        {trend !== null && trend !== undefined && (
          <div className={cn("flex items-center gap-1", trendColor)}>
            <TrendIcon className="h-3.5 w-3.5" />
            <span className="font-mono text-xs font-semibold">
              {trend > 0 ? "+" : ""}
              {trend.toFixed(1)}
            </span>
          </div>
        )}
      </div>

      {data.confidence < 0.5 && (
        <div className="mb-3 flex items-start gap-1.5 rounded-card border border-warning/30 bg-warning/5 p-2 text-[10px] text-warning">
          <Info className="mt-0.5 h-3 w-3 shrink-0" />
          {t.coldStartWarning}
        </div>
      )}

      <div className="space-y-2.5">
        <SubScoreBar label={t.breakdown.fuel} value={data.fuel_score} />
        <SubScoreBar
          label={t.breakdown.maintenance}
          value={data.maintenance_score}
        />
        <SubScoreBar label={t.breakdown.driver} value={data.driver_score} />
        <SubScoreBar
          label={t.breakdown.anomaly}
          value={data.anomaly_quality_score}
        />
      </div>

      <div className="mt-3 flex items-center justify-between text-[10px] text-tertiary">
        <span>
          {t.confidence}:{" "}
          <span className="font-mono">
            {(data.confidence * 100).toFixed(0)}%
          </span>
        </span>
      </div>
    </div>
  );
}
