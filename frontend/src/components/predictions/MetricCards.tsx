import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui/Card";

interface Props {
  mae: number;
  rmse: number;
  totalCompared: number;
  goodPct: number;
}

export function MetricCards({ mae, rmse, totalCompared, goodPct }: Props) {
  const { t } = useTranslation();

  const metrics = [
    {
      label: "MAE",
      value: mae.toFixed(2),
      unit: "L/100km",
      color: "text-blue-500",
    },
    {
      label: "RMSE",
      value: rmse.toFixed(2),
      unit: "L/100km",
      color: "text-purple-500",
    },
    {
      label: t("predictions.accuracy_label", "Accuracy"),
      value: `${goodPct.toFixed(0)}%`,
      unit: t("predictions.good_prediction", "good predictions"),
      color: "text-emerald-500",
    },
    {
      label: t("predictions.compared_label", "Compared"),
      value: totalCompared.toString(),
      unit: t("predictions.trip_unit", "trips"),
      color: "text-secondary",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {metrics.map((m) => (
        <Card key={m.label} padding="md">
          <p className="text-[11px] font-bold uppercase tracking-wider text-secondary">
            {m.label}
          </p>
          <p className={`mt-1 text-2xl font-bold ${m.color}`}>{m.value}</p>
          <p className="text-xs text-tertiary">{m.unit}</p>
        </Card>
      ))}
    </div>
  );
}
