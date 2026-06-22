import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "../ui/Card";
import { chartTheme } from "../../lib/chart-theme";
import { reportService } from "../../api/reports";

interface ChartPoint {
  label: string;
  fuel_liters: number;
  unit_price: number;
}

function buildPoints(
  rows: Awaited<ReturnType<typeof reportService.getCostAnalysis>>,
): ChartPoint[] {
  return rows
    .map((r) => ({
      label: r.label,
      fuel_liters: Number(r.fuel_liters ?? 0),
      unit_price:
        r.fuel_liters && r.fuel_liters > 0
          ? Number(r.fuel_cost) / Number(r.fuel_liters)
          : 0,
    }))
    .filter((p) => p.fuel_liters > 0 || p.unit_price > 0);
}

export function CostTrendChart() {
  const {
    data: rows,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["costTrend", 12],
    queryFn: () => reportService.getCostAnalysis(12),
    staleTime: 10 * 60 * 1000,
  });

  const points = rows ? buildPoints(rows) : [];

  return (
    <Card padding="lg">
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-primary">Maliyet Trendi</h2>
        <p className="text-xs text-secondary">
          Aylık toplam litre ve litre başına ortalama fiyat
        </p>
      </div>

      {isLoading ? (
        <div className="h-36 animate-pulse rounded-card bg-elevated/50" />
      ) : isError ? (
        <p className="text-sm text-secondary">Maliyet trendi yüklenemedi</p>
      ) : points.length === 0 ? (
        <p className="text-sm text-secondary">
          Bu dönem için gösterilecek maliyet verisi yok
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={144}>
          <LineChart
            data={points}
            margin={{ top: 5, right: 12, left: -10, bottom: 0 }}
          >
            <CartesianGrid {...chartTheme.grid} />
            <XAxis
              dataKey="label"
              tick={chartTheme.tickSmall}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              yAxisId="left"
              tick={chartTheme.tick}
              unit=" L"
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={chartTheme.tick}
              unit=" ₺"
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              {...chartTheme.tooltip}
              formatter={(value, name) => {
                const num = Number(value ?? 0);
                if (name === "Litre") {
                  return [
                    `${num.toLocaleString("tr-TR", {
                      maximumFractionDigits: 0,
                    })} L`,
                    name,
                  ];
                }
                return [
                  `${num.toLocaleString("tr-TR", {
                    maximumFractionDigits: 2,
                  })} ₺/L`,
                  name,
                ];
              }}
            />
            <Legend
              iconType="circle"
              wrapperStyle={{ fontSize: 11, color: "var(--text-secondary)" }}
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="fuel_liters"
              name="Litre"
              stroke={chartTheme.colors.accent}
              strokeWidth={2}
              dot={false}
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="unit_price"
              name="Birim Fiyat (₺/L)"
              stroke={chartTheme.colors.warning}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}
