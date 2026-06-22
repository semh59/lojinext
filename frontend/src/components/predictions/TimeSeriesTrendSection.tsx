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
import { Card } from "@/components/ui/Card";
import { chartTheme } from "@/lib/chart-theme";
import { predictionService } from "@/api/predictions";

interface TimeSeriesTrendSectionProps {
  aracId?: number | null;
  days?: number;
}

const TREND_META = {
  increasing: {
    label: "Yükselişte",
    icon: ArrowUpRight,
    accent: "text-danger",
    hint: "Son dönemde tüketim artıyor; performans takibi tavsiye edilir.",
  },
  decreasing: {
    label: "Düşüşte",
    icon: ArrowDownRight,
    accent: "text-success",
    hint: "Son dönemde tüketim azalıyor — pozitif sinyal.",
  },
  stable: {
    label: "Stabil",
    icon: Minus,
    accent: "text-warning",
    hint: "Tüketim son dönemde anlamlı bir değişim göstermiyor.",
  },
} as const;

export function TimeSeriesTrendSection({
  aracId,
  days = 30,
}: TimeSeriesTrendSectionProps) {
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
            Son {days} Gün Trendi
          </h2>
          <p className="text-xs text-secondary">
            Tarihsel tüketim trendi; modelin geriye dönük analizi.
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 py-6 text-secondary text-sm">
          <Loader2 className="h-4 w-4 animate-spin" /> Trend hesaplanıyor…
        </div>
      ) : isError || !data?.success ? (
        <p className="text-sm text-secondary">
          Trend analizi şu an üretilemiyor (yeterli geçmiş veri yok).
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
                          Trend:{" "}
                        </span>
                        <span className={meta.accent}>{meta.label}</span>
                        {typeof data.slope === "number" && (
                          <span className="ml-2 font-mono text-[11px] text-secondary">
                            eğim {data.slope.toFixed(3)} L/100km/gün
                          </span>
                        )}
                      </p>
                      <p className="text-[11px] text-secondary">{meta.hint}</p>
                    </div>
                    {typeof data.avg === "number" && (
                      <div className="text-right">
                        <p className="text-[9px] font-bold uppercase tracking-widest text-secondary">
                          Ortalama
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
                      "Tüketim",
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
