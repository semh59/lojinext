import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowDownRight,
  ArrowUpRight,
  CalendarRange,
  Loader2,
  Minus,
  AlertCircle,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui/Card";
import { chartTheme } from "@/lib/chart-theme";
import { predictionService } from "@/api/predictions";
import { vehicleService } from "@/api/vehicles";

export function TimeSeriesForecast() {
  const { t } = useTranslation();
  const [aracId, setAracId] = useState<number | null>(null);

  const TREND_META = {
    increasing: {
      label: t("predictions.trend_rising", "Rising"),
      icon: ArrowUpRight,
      accent: "text-danger",
    },
    decreasing: {
      label: t("predictions.trend_falling", "Falling"),
      icon: ArrowDownRight,
      accent: "text-success",
    },
    stable: {
      label: t("predictions.trend_stable", "Stable"),
      icon: Minus,
      accent: "text-warning",
    },
  } as const;

  const { data: vehiclesData } = useQuery({
    queryKey: ["ts-vehicles"],
    queryFn: () => vehicleService.getAll({ aktif_only: true, limit: 200 }),
    staleTime: 10 * 60 * 1000,
  });
  const vehicles = (vehiclesData?.items ?? []) as Array<{
    id: number;
    plaka: string;
  }>;

  const forecast = useMutation({
    mutationFn: () =>
      predictionService.timeSeriesForecast(aracId ?? undefined, 7),
  });

  const trendQuery = useQuery({
    queryKey: ["ts-trend", aracId],
    queryFn: () => predictionService.timeSeriesTrend(aracId ?? undefined, 30),
    staleTime: 5 * 60 * 1000,
    enabled: false,
  });

  const chartData = useMemo(() => {
    const series = forecast.data?.series ?? [];
    return series.map((p) => ({
      date: p.date,
      value: Number(p.value ?? 0),
      confidence_low:
        p.confidence_low != null ? Number(p.confidence_low) : null,
      confidence_high:
        p.confidence_high != null ? Number(p.confidence_high) : null,
    }));
  }, [forecast.data]);

  const handleForecast = () => {
    forecast.mutate();
    trendQuery.refetch();
  };

  const trendDir = forecast.data?.trend;
  const trendMeta = trendDir ? TREND_META[trendDir] : null;
  const TrendIcon = trendMeta?.icon;

  return (
    <Card padding="lg" className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <CalendarRange className="h-5 w-5 text-accent" />
          <div>
            <h2 className="text-sm font-semibold text-primary">
              {t("predictions.weekly_title", "Weekly Forecast")}
            </h2>
            <p className="text-xs text-secondary">
              {t(
                "predictions.weekly_subtitle",
                "7-day consumption projection + confidence interval",
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-[11px] font-bold uppercase tracking-widest text-secondary">
            {t("predictions.xai_vehicle_label", "Vehicle")}
          </label>
          <select
            className="input-base !w-44"
            value={aracId ?? ""}
            onChange={(e) =>
              setAracId(e.target.value ? Number(e.target.value) : null)
            }
          >
            <option value="">{t("predictions.fleet_all", "All Fleet")}</option>
            {vehicles.map((v) => (
              <option key={v.id} value={v.id}>
                {v.plaka}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={handleForecast}
            disabled={forecast.isPending}
            className="rounded-card bg-accent px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-accent/90 disabled:opacity-50"
          >
            {forecast.isPending ? (
              <span className="inline-flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                {t("predictions.calculating", "Calculating…")}
              </span>
            ) : (
              t("predictions.forecast_btn", "Forecast")
            )}
          </button>
        </div>
      </div>

      {forecast.isError && (
        <div className="flex items-center gap-2 rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          <AlertCircle className="h-4 w-4" />
          {t(
            "predictions.forecast_error",
            "Could not create forecast. Model may not have enough training data.",
          )}
        </div>
      )}

      {forecast.data && chartData.length > 0 ? (
        <>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={chartData}
                margin={{ top: 8, right: 12, left: -10, bottom: 0 }}
              >
                <defs>
                  <linearGradient
                    id="confidenceBand"
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="0%"
                      stopColor="var(--accent)"
                      stopOpacity={0.2}
                    />
                    <stop
                      offset="100%"
                      stopColor="var(--accent)"
                      stopOpacity={0}
                    />
                  </linearGradient>
                </defs>
                <CartesianGrid {...chartTheme.grid} />
                <XAxis
                  dataKey="date"
                  tick={chartTheme.tickSmall}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={chartTheme.tick}
                  unit=" L"
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  {...chartTheme.tooltip}
                  formatter={(value) => [
                    `${Number(value ?? 0).toFixed(1)} L`,
                    t("predictions.forecast_series_name", "Forecast"),
                  ]}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Area
                  type="monotone"
                  dataKey="confidence_high"
                  stroke="transparent"
                  fill="url(#confidenceBand)"
                  name={t(
                    "predictions.confidence_upper",
                    "Upper confidence band",
                  )}
                />
                <Area
                  type="monotone"
                  dataKey="confidence_low"
                  stroke="transparent"
                  fill="var(--surface)"
                  name={t(
                    "predictions.confidence_lower",
                    "Lower confidence band",
                  )}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={chartTheme.colors.accent}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  name={t("predictions.forecast_series_name", "Forecast")}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {trendMeta && TrendIcon && (
            <div className="flex items-center gap-2 rounded-card border border-border/60 bg-elevated/30 px-4 py-3">
              <TrendIcon className={`h-5 w-5 ${trendMeta.accent}`} />
              <div className="text-xs">
                <span className="font-semibold text-primary">
                  {t("predictions.trend_label_inline", "Trend:")}{" "}
                </span>
                <span className={trendMeta.accent}>{trendMeta.label}</span>
                {forecast.data.method && (
                  <span className="ml-2 text-secondary">
                    · {t("predictions.trend_method_label", "method:")}{" "}
                    <span className="font-mono">{forecast.data.method}</span>
                  </span>
                )}
              </div>
            </div>
          )}

          {forecast.data.summary && (
            <p className="text-[11px] text-secondary">
              {forecast.data.summary}
            </p>
          )}
        </>
      ) : (
        <p className="text-sm text-secondary">
          {forecast.isPending
            ? ""
            : t(
                "predictions.hint_use_button",
                'Use the "Predict" button to generate the projection.',
              )}
        </p>
      )}
    </Card>
  );
}
