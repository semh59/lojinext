import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Card } from "@/components/ui/Card";
import { chartTheme } from "@/lib/chart-theme";
import type { EnsembleStatusResponse } from "@/api/predictions";

const MODEL_LABELS: Record<string, string> = {
  physics: "Fizik",
  lightgbm: "LightGBM",
  xgboost: "XGBoost",
  gradient_boosting: "Grad. Boost",
  random_forest: "Rand. Forest",
};

export function EnsembleStatusCard({ data }: { data: EnsembleStatusResponse }) {
  const chartData = Object.entries(data.weights).map(([key, weight]) => ({
    name: MODEL_LABELS[key] ?? key,
    weight: Math.round(weight * 100),
    available: data.models[key] ?? false,
  }));

  return (
    <Card padding="lg" className="flex flex-col gap-4">
      <div>
        <h2 className="text-sm font-semibold text-primary">
          Ensemble Model Ağırlıkları
        </h2>
        <p className="text-xs text-secondary">
          {data.total_models} aktif model
        </p>
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={chartData} layout="vertical">
          <XAxis
            type="number"
            unit="%"
            tick={chartTheme.tick}
            domain={[0, 100]}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={chartTheme.tick}
            width={90}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            {...chartTheme.tooltip}
            formatter={(v: number | undefined) => [
              v != null ? `${v}%` : "",
              "Ağırlık",
            ]}
          />
          <Bar dataKey="weight" radius={[0, 4, 4, 0]}>
            {chartData.map((entry, index) => (
              <Cell
                key={index}
                fill={
                  entry.available
                    ? chartTheme.colors.accent
                    : chartTheme.colors.border
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
