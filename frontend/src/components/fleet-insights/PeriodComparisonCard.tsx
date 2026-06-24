import {
  AlertCircle,
  AlertTriangle,
  Fuel,
  Loader2,
  Receipt,
  Route as RouteIcon,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import { cn } from "@/lib/utils";
import { useFleetComparison } from "@/hooks/useFleetInsights";
import type { PeriodMetrics, PeriodType } from "@/api/fleet-insights";

interface Props {
  period: PeriodType;
  className?: string;
}

interface RowProps {
  Icon: typeof Fuel;
  label: string;
  current: number;
  previous: number;
  deltaPct: number | null;
  unit: string;
  /** Düşük değer iyi mi? (yakıt için true; sefer sayısı için false) */
  lowerIsBetter: boolean;
}

function MetricRow({
  Icon,
  label,
  current,
  previous,
  deltaPct,
  unit,
  lowerIsBetter,
}: RowProps) {
  const { t, i18n } = useTranslation();
  const locale = (i18n.language ?? "tr").startsWith("en") ? "en-US" : "tr-TR";
  const hasData = deltaPct !== null;
  const isImprovement = hasData
    ? lowerIsBetter
      ? deltaPct < 0
      : deltaPct > 0
    : null;

  const TrendIcon =
    deltaPct === null
      ? AlertTriangle
      : deltaPct === 0
        ? AlertTriangle
        : deltaPct > 0
          ? TrendingUp
          : TrendingDown;

  const trendColor =
    deltaPct === null
      ? "text-tertiary"
      : isImprovement
        ? "text-success"
        : "text-danger";

  return (
    <div className="flex items-center justify-between rounded-card border border-border/40 bg-elevated/30 px-3 py-2.5">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-secondary" />
        <div>
          <p className="text-[10px] uppercase tracking-wider text-tertiary">
            {label}
          </p>
          <p className="font-mono text-sm font-bold tabular-nums text-primary">
            {current.toLocaleString(locale)}{" "}
            <span className="text-[10px] text-tertiary">{unit}</span>
          </p>
        </div>
      </div>
      <div className="flex flex-col items-end">
        {hasData ? (
          <span
            className={cn(
              "inline-flex items-center gap-1 font-mono text-xs font-semibold",
              trendColor,
            )}
          >
            <TrendIcon className="h-3 w-3" />
            {deltaPct > 0 ? "+" : ""}
            {deltaPct.toFixed(1)}%
          </span>
        ) : (
          <span className="text-[10px] text-tertiary italic">
            {t("nav.no_data", "No data")}
          </span>
        )}
        <span className="font-mono text-[10px] text-tertiary">
          {t("common.previous", "Prev.")}: {previous.toLocaleString(locale)}
        </span>
      </div>
    </div>
  );
}

export function PeriodComparisonCard({ period, className }: Props) {
  const { data, isLoading, error } = useFleetComparison(period);

  const { t } = useTranslation();

  if (isLoading) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 rounded-modal border border-border bg-surface p-6 shadow-sm",
          className,
        )}
      >
        <Loader2 className="h-4 w-4 animate-spin text-secondary" />
        <span className="text-sm text-secondary">
          {t("fleet.comparison_loading", "Loading comparison…")}
        </span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div
        className={cn(
          "flex items-start gap-2 rounded-modal border border-danger/30 bg-danger/5 p-4 text-sm text-danger",
          className,
        )}
      >
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
        {t("fleet.comparison_error", "Comparison could not be loaded")}
      </div>
    );
  }

  const periodLabel =
    period === "week"
      ? t("fleet.period_week", "This Week")
      : t("fleet.period_month", "This Month");

  return (
    <div
      className={cn(
        "rounded-modal border border-border bg-surface p-6 shadow-sm",
        className,
      )}
    >
      <div className="mb-4">
        <h3 className="text-xs font-bold uppercase tracking-widest text-secondary">
          {periodLabel} {t("fleet.period_vs_prev", "vs Last")}
        </h3>
        <p className="mt-0.5 text-[10px] text-tertiary">
          {data.current_start} → {data.current_end}
        </p>
      </div>

      <div className="space-y-2">
        <MetricRow
          Icon={Fuel}
          label={t("fleet.metric_fuel", "Fuel")}
          current={data.current.fuel_l}
          previous={data.previous.fuel_l}
          deltaPct={data.fuel_l_delta_pct}
          unit="L"
          lowerIsBetter
        />
        <MetricRow
          Icon={Receipt}
          label={t("fleet.metric_fuel_cost", "Fuel Cost")}
          current={data.current.fuel_cost_tl}
          previous={data.previous.fuel_cost_tl}
          deltaPct={data.fuel_cost_delta_pct}
          unit="₺"
          lowerIsBetter
        />
        <MetricRow
          Icon={RouteIcon}
          label={t("fleet.metric_trips", "Completed Trips")}
          current={data.current.trip_count}
          previous={data.previous.trip_count}
          deltaPct={data.trip_delta_pct}
          unit=""
          lowerIsBetter={false}
        />
        <MetricRow
          Icon={AlertTriangle}
          label={t("fleet.metric_anomalies", "Anomalies (priority)")}
          current={data.current.anomaly_count}
          previous={data.previous.anomaly_count}
          deltaPct={data.anomaly_delta_pct}
          unit=""
          lowerIsBetter
        />
      </div>
    </div>
  );
}

// Helper getter exposed for tests
export { type PeriodMetrics };
