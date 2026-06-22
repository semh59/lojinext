import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui/Card";
import { chartTheme } from "@/lib/chart-theme";

interface TrendPoint {
  date: string;
  actual: number;
  predicted: number;
}

export function AccuracyChart({ data }: { data: TrendPoint[] }) {
  const { t } = useTranslation();

  return (
    <Card padding="lg" className="flex flex-col gap-4">
      <div>
        <h2 className="text-sm font-semibold text-primary">
          {t("predictions.actual_vs_predicted", "Actual vs Predicted")}
        </h2>
        <p className="text-xs text-secondary">
          {t("predictions.last_30_days", "Last 30 days, L/100km")}
        </p>
      </div>
      {data.length === 0 ? (
        <div className="flex h-48 items-center justify-center text-sm text-secondary">
          {t("predictions.no_data", "No data")}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={192}>
          <AreaChart data={data}>
            <defs>
              <linearGradient id="actualGrad" x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="5%"
                  stopColor={chartTheme.colors.info}
                  stopOpacity={0.2}
                />
                <stop
                  offset="95%"
                  stopColor={chartTheme.colors.info}
                  stopOpacity={0}
                />
              </linearGradient>
              <linearGradient id="predictedGrad" x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="5%"
                  stopColor={chartTheme.colors.success}
                  stopOpacity={0.2}
                />
                <stop
                  offset="95%"
                  stopColor={chartTheme.colors.success}
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
            <Tooltip {...chartTheme.tooltip} />
            <Legend
              wrapperStyle={{
                fontSize: "11px",
                color: "var(--text-secondary)",
              }}
            />
            <Area
              type="monotone"
              dataKey="actual"
              name={t("predictions.actual_series", "Actual")}
              stroke={chartTheme.colors.info}
              fill="url(#actualGrad)"
              strokeWidth={2}
              dot={false}
            />
            <Area
              type="monotone"
              dataKey="predicted"
              name={t("predictions.forecast_series_name", "Forecast")}
              stroke={chartTheme.colors.success}
              fill="url(#predictedGrad)"
              strokeWidth={2}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}
