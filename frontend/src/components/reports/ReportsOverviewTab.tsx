import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

import { reportService } from "@/api/reports";
import { useReportsResources } from "@/resources/useResources";
import { cn } from "@/lib/utils";

function TrendBadge({ pct }: { pct: number | undefined }) {
  const { reportPageText } = useReportsResources();
  const t = reportPageText.overviewKpi;
  if (pct === undefined || pct === null) {
    return <span className="text-xs text-tertiary">{t.trendNeutral}</span>;
  }
  const isUp = pct > 0;
  const isFlat = pct === 0;
  return (
    <span
      className={cn(
        "flex items-center gap-0.5 text-xs font-medium",
        isFlat ? "text-tertiary" : isUp ? "text-green-500" : "text-red-500",
      )}
    >
      {isFlat ? (
        <Minus className="h-3 w-3" />
      ) : isUp ? (
        <TrendingUp className="h-3 w-3" />
      ) : (
        <TrendingDown className="h-3 w-3" />
      )}
      {t.trend(pct)}
    </span>
  );
}

export function ReportsOverviewTab() {
  const { reportPageText } = useReportsResources();
  const t = reportPageText.overviewKpi;

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["reports-dashboard-stats"],
    queryFn: () => reportService.getDashboardStats(),
    staleTime: 5 * 60 * 1000,
  });

  const { data: trend = [], isLoading: trendLoading } = useQuery({
    queryKey: ["reports-consumption-trend"],
    queryFn: () => reportService.getConsumptionTrend(),
    staleTime: 5 * 60 * 1000,
  });

  const kpiCards = [
    {
      label: t.totalTrips,
      value: stats?.toplam_sefer ?? "—",
      trend: stats?.trends?.sefer,
      unit: "",
    },
    {
      label: t.totalKm,
      value: stats
        ? `${stats.toplam_km.toLocaleString("tr-TR", {
            maximumFractionDigits: 0,
          })}`
        : "—",
      trend: stats?.trends?.km,
      unit: "km",
    },
    {
      label: t.fleetAvg,
      value: stats ? `${stats.filo_ortalama.toFixed(1)}` : "—",
      trend: stats?.trends?.tuketim,
      unit: "L/100km",
    },
    {
      label: t.todayTrips,
      value: stats?.bugun_sefer ?? "—",
      trend: undefined,
      unit: "",
    },
  ];

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {kpiCards.map((card) => (
          <div
            key={card.label}
            className="flex flex-col gap-1 rounded-card border border-border bg-elevated/40 p-4"
          >
            <span className="text-xs text-secondary">{card.label}</span>
            {statsLoading ? (
              <div className="h-7 w-20 animate-pulse rounded bg-elevated" />
            ) : (
              <span className="text-2xl font-bold text-primary">
                {card.value}
                {card.unit && (
                  <span className="ml-1 text-sm font-normal text-secondary">
                    {card.unit}
                  </span>
                )}
              </span>
            )}
            <TrendBadge pct={card.trend} />
          </div>
        ))}
      </div>

      {/* Consumption Trend Chart */}
      <div className="rounded-card border border-border bg-elevated/20 p-4">
        <h3 className="mb-4 text-sm font-semibold text-primary">
          {t.consumptionTitle}
        </h3>
        {trendLoading ? (
          <div className="flex h-48 items-center justify-center text-sm text-secondary">
            {t.loading}
          </div>
        ) : trend.length === 0 ? (
          <p className="py-12 text-center text-sm text-secondary">
            {t.consumptionEmpty}
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={trend}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="var(--border)"
                opacity={0.5}
              />
              <XAxis
                dataKey="month"
                tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={55}
              />
              <Tooltip
                formatter={(v: number | undefined) => [
                  v != null
                    ? `${v.toLocaleString("tr-TR", {
                        maximumFractionDigits: 0,
                      })} ${t.consumptionUnit}`
                    : "",
                  t.consumptionUnit,
                ]}
                contentStyle={{
                  backgroundColor: "var(--bg-surface)",
                  border: "1px solid var(--border)",
                  borderRadius: "8px",
                }}
                itemStyle={{ color: "var(--text-primary)" }}
                labelStyle={{ color: "var(--text-secondary)" }}
              />
              <Bar
                dataKey="consumption"
                fill="var(--accent)"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
