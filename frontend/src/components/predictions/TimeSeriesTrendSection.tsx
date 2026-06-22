import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowDownRight,
  ArrowUpRight,
  Loader2,
  Minus,
  TrendingUp,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui/Card";
import { chartTheme } from "@/lib/chart-theme";
import { predictionService } from "@/api/predictions";

interface TimeSeriesTrendSectionProps {
  aracId?: number | null;
  days?: number;
}

export function TimeSeriesTrendSection({
  aracId,
  days = 30,
}: TimeSeriesTrendSectionProps) {
  const { t } = useTranslation();

  const TREND_META = {
    increasing: {
      label: t("predictions.trend_rising", "Rising"),
      icon: ArrowUpRight,
      accent: "text-danger",
      hint: t(
        "predictions.trend_hint_rising",
        "Consumption is increasing recently; performance monitoring recommended.",
      ),
    },
    decreasing: {
      label: t("predictions.trend_falling", "Falling"),
      icon: ArrowDownRight,
      accent: "text-success",
      hint: t(
        "predictions.trend_hint_falling",
        "Consumption is decreasing — positive signal.",
      ),
    },
    stable: {
      label: t("predictions.trend_stable", "Stable"),
      icon: Minus,
      accent: "text-warning",
      hint: t(
        "predictions.trend_hint_stable",
        "No significant change in consumption recently.",
      ),
    },
  } as const;

  const { data, isLoading, isError } = useQuery({
    queryKey: ["ts-trend", aracId ?? null, days],
    queryFn: () => predictionService.timeSeriesTrend(aracId ?? undefined, days),
    staleTime: 5 * 60 * 1000,
  });

  return (
    <Card padding="lg" className="space-y-4">
      <div className="flex items-center gap-2">
        <TrendingUp className="h-5 w-5 text-accent" />
        <div>
          <h2 className="text-sm font-semibold text-primary">
            {t("predictions.trend_days_title", "Last {{days}} Days Trend", {
              days,
            })}
          </h2>
          <p className="text-xs text-secondary">
            {t(
              "predictions.trend_subtitle",
              "Historical consumption trend; model's retrospective analysis.",
            )}
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 py-6 text-secondary text-sm">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t("predictions.trend_loading", "Calculating trend…")}
        </div>
      ) : isError || !data?.success ? (
        <p className="text-sm text-secondary">
          {t(
            "predictions.trend_na",
            "Trend analysis cannot be produced (insufficient historical data).",
          )}
        </p>
      ) : (
        <>
          {data.trend && TREND_META[data.trend] && (
            <div className="flex items-center gap-3 rounded-card border border-border/60 bg-elevated/30 px-4 py-3">
              {(() => {
                const meta = TREND_META[data.trend as keyof typeof TREND_META];
                const Icon = meta.icon;
                return (
                  <>
                    <Icon className={`h-5 w-5 ${meta.accent}`} />
                    <div className="flex-1">
                      <p className="text-sm">
                        <span className="font-semibold text-primary">
                          {t("predictions.trend_label_inline", "Trend:")}{" "}
                        </span>
                        <span className={meta.accent}>{meta.label}</span>
                        {typeof data.slope === "number" && (
                          <span className="ml-2 font-mono text-[11px] text-secondary">
                            {t(
                              "predictions.trend_slope",
                              "slope {{n}} L/100km/day",
                              {
                                n: data.slope.toFixed(3),
                              },
                            )}
                          </span>
                        )}
                      </p>
                      <p className="text-[11px] text-secondary">{meta.hint}</p>
                    </div>
                    {typeof data.avg === "number" && (
                      <div className="text-right">
                        <p className="text-[9px] font-bold uppercase tracking-widest text-secondary">
                          {t("predictions.trend_average", "Average")}
                        </p>
                        <p className="text-sm font-mono font-semibold text-primary">
                          {data.avg.toFixed(1)} L/100km
                        </p>
                      </div>
                    )}
                  </>
                );
              })()}
            </div>
          )}

          {Array.isArray(data.series) && data.series.length > 0 && (
            <div className="h-48 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={data.series}
                  margin={{ top: 8, right: 12, left: -10, bottom: 0 }}
                >
                  <defs>
                    <linearGradient
                      id="trendGradient"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop
                        offset="0%"
                        stopColor="var(--accent)"
                        stopOpacity={0.25}
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
                      `${Number(value ?? 0).toFixed(1)} L/100km`,
                      t("predictions.consumption_label", "Consumption"),
                    ]}
                  />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke={chartTheme.colors.accent}
                    strokeWidth={2}
                    fill="url(#trendGradient)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
