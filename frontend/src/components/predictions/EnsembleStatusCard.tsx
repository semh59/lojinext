import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui/Card";
import { chartTheme } from "@/lib/chart-theme";
import type { EnsembleStatusResponse } from "@/api/predictions";

export function EnsembleStatusCard({ data }: { data: EnsembleStatusResponse }) {
  const { t } = useTranslation();

  const MODEL_LABELS: Record<string, string> = {
    physics: t("predictions.model_label_physics", "Physics"),
    lightgbm: "LightGBM",
    xgboost: "XGBoost",
    gradient_boosting: "Grad. Boost",
    random_forest: "Rand. Forest",
  };

  const chartData = Object.entries(data.weights).map(([key, weight]) => ({
    name: MODEL_LABELS[key] ?? key,
    weight: Math.round(weight * 100),
    available: data.models[key] ?? false,
  }));

  return (
    <Card padding="lg" className="flex flex-col gap-4">
      <div>
        <h2 className="text-sm font-semibold text-primary">
          {t("predictions.ensemble_weights_title", "Ensemble Model Weights")}
        </h2>
        <p className="text-xs text-secondary">
          {t("predictions.ensemble_active_models", "{{n}} active models", {
            n: data.total_models,
          })}
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
              t("predictions.weight_label", "Weight"),
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
