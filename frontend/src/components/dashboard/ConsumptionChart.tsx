import { useTranslation } from "react-i18next";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card } from "@/components/ui/Card";
import { chartTheme } from "@/lib/chart-theme";
import { useLocale } from "../../hooks/useLocale";

interface Props {
  data: Array<{ month: string; consumption: number }>;
  isLoading?: boolean;
}

export function ConsumptionChart({ data, isLoading }: Props) {
  const { t } = useTranslation();
  const locale = useLocale();
  return (
    <Card padding="lg" className="flex flex-col gap-4">
      <div>
        <h2 className="text-sm font-semibold text-primary">
          {t("dashboard.consumption_trend")}
        </h2>
        <p className="text-xs text-secondary">{t("dashboard.monthly_fuel")}</p>
      </div>
      {isLoading ? (
        <div className="h-48 animate-pulse rounded-card bg-elevated/50" />
      ) : data.length === 0 ? (
        <div className="flex h-48 items-center justify-center text-sm text-secondary">
          {t("dashboard.no_data_yet")}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={192}>
          <LineChart data={data}>
            <CartesianGrid {...chartTheme.grid} />
            <XAxis
              dataKey="month"
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
              formatter={(v: number | undefined) => [
                v != null
                  ? `${v.toLocaleString(locale, {
                      maximumFractionDigits: 1,
                    })} L`
                  : "",
                t("dashboard.consumption"),
              ]}
            />
            <Line
              type="monotone"
              dataKey="consumption"
              stroke={chartTheme.colors.accent}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}
