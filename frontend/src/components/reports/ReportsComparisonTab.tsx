import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

import { reportService, type FleetComparisonPeriod } from "@/api/reports";
import { useReportsResources } from "@/resources/useResources";
import { cn } from "@/lib/utils";

function DeltaBadge({ pct }: { pct: number | null | undefined }) {
  if (pct === null || pct === undefined) {
    return <span className="text-xs text-tertiary">—</span>;
  }
  const isUp = pct > 0;
  const isFlat = Math.abs(pct) < 0.05;
  return (
    <span
      className={cn(
        "flex items-center gap-0.5 text-xs font-semibold",
        isFlat ? "text-tertiary" : isUp ? "text-red-500" : "text-green-500",
      )}
    >
      {isFlat ? (
        <Minus className="h-3 w-3" />
      ) : isUp ? (
        <TrendingUp className="h-3 w-3" />
      ) : (
        <TrendingDown className="h-3 w-3" />
      )}
      {pct > 0 ? "+" : ""}
      {pct.toFixed(1)}%
    </span>
  );
}

function MetricRow({
  label,
  current,
  previous,
  deltaPct,
  unit,
}: {
  label: string;
  current: number;
  previous: number;
  deltaPct: number | null | undefined;
  unit: string;
}) {
  const fmt = (v: number) =>
    v.toLocaleString("tr-TR", { maximumFractionDigits: 1 });

  return (
    <div className="grid grid-cols-4 items-center gap-2 rounded-card border border-border/50 bg-elevated/20 px-4 py-3">
      <span className="text-sm text-secondary">{label}</span>
      <span className="text-right text-sm font-semibold text-primary">
        {fmt(current)}
        <span className="ml-1 text-xs font-normal text-tertiary">{unit}</span>
      </span>
      <span className="text-right text-sm text-tertiary">
        {fmt(previous)}
        <span className="ml-1 text-xs">{unit}</span>
      </span>
      <div className="flex justify-end">
        <DeltaBadge pct={deltaPct} />
      </div>
    </div>
  );
}

export function ReportsComparisonTab() {
  const { reportPageText } = useReportsResources();
  const t = reportPageText.comparison;
  const [period, setPeriod] = useState<FleetComparisonPeriod>("month");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["fleet-comparison", period],
    queryFn: () => reportService.getFleetComparison(period),
    staleTime: 3 * 60 * 1000,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-primary">{t.title}</h2>
          <p className="text-sm text-secondary">{t.subtitle}</p>
        </div>
        <div className="flex gap-1 rounded-card border border-border bg-elevated/40 p-1">
          {(["week", "month"] as FleetComparisonPeriod[]).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={cn(
                "rounded-card px-3 py-1.5 text-xs font-medium transition-colors",
                period === p
                  ? "bg-accent text-white shadow-sm"
                  : "text-secondary hover:text-primary",
              )}
            >
              {p === "week" ? t.week : t.month}
            </button>
          ))}
        </div>
      </div>

      {/* Column Headers */}
      <div className="grid grid-cols-4 gap-2 px-4 text-xs font-semibold uppercase tracking-wider text-tertiary">
        <span>Metrik</span>
        <span className="text-right">{t.current}</span>
        <span className="text-right">{t.previous}</span>
        <span className="text-right">Δ</span>
      </div>

      {isLoading && (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-12 animate-pulse rounded-card bg-elevated/40"
            />
          ))}
        </div>
      )}

      {isError && (
        <p className="py-8 text-center text-sm text-secondary">{t.noData}</p>
      )}

      {data && !isLoading && (
        <div className="space-y-2">
          <MetricRow
            label={t.trips}
            current={data.current.trip_count}
            previous={data.previous.trip_count}
            deltaPct={data.trip_delta_pct}
            unit=""
          />
          <MetricRow
            label={t.fuelL}
            current={data.current.fuel_l}
            previous={data.previous.fuel_l}
            deltaPct={data.fuel_l_delta_pct}
            unit="L"
          />
          <MetricRow
            label={t.fuelCost}
            current={data.current.fuel_cost_tl}
            previous={data.previous.fuel_cost_tl}
            deltaPct={data.fuel_cost_delta_pct}
            unit="₺"
          />
          <MetricRow
            label={t.anomalies}
            current={data.current.anomaly_count}
            previous={data.previous.anomaly_count}
            deltaPct={data.anomaly_delta_pct}
            unit=""
          />
        </div>
      )}

      {data && (
        <p className="text-right text-xs text-tertiary">
          {data.current_start} – {data.current_end}
        </p>
      )}
    </div>
  );
}
