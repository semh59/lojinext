import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui/Card";
import { Activity, CheckCircle2, AlertTriangle } from "lucide-react";
import { predictionService } from "@/api/predictions";

export function TimeSeriesStatusCard() {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: ["ts-status"],
    queryFn: () => predictionService.timeSeriesStatus(),
    staleTime: 5 * 60 * 1000,
  });

  const isAvailable = Boolean(
    (data as any)?.available ?? (data as any)?.model_trained ?? false,
  );
  const method = (data as any)?.method ?? "—";
  const historyDays = (data as any)?.history_days;

  return (
    <Card padding="lg" className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Activity className="h-5 w-5 text-accent" />
        <h2 className="text-sm font-semibold text-primary">
          {t("predictions.ts_model_title", "Time Series Model")}
        </h2>
      </div>

      {isLoading ? (
        <div className="h-10 animate-pulse rounded-card bg-elevated/40" />
      ) : isAvailable ? (
        <div className="flex items-center gap-3 rounded-card border border-success/20 bg-success/5 px-4 py-3">
          <CheckCircle2 className="h-5 w-5 text-success" />
          <div>
            <p className="text-sm font-semibold text-primary">
              {t("predictions.ts_ready", "Ready")}
            </p>
            <p className="text-[11px] text-secondary">
              {t("predictions.ts_method_label", "Method:")}{" "}
              <span className="font-mono">{method}</span>
              {typeof historyDays === "number" &&
                t("predictions.ts_history_days", " · {{n}} days of history", {
                  n: historyDays,
                })}
            </p>
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-3 rounded-card border border-warning/20 bg-warning/5 px-4 py-3">
          <AlertTriangle className="h-5 w-5 text-warning" />
          <div>
            <p className="text-sm font-semibold text-primary">
              {t("predictions.ts_insufficient_data", "Insufficient data")}
            </p>
            <p className="text-[11px] text-secondary">
              {t(
                "predictions.ts_insufficient_hint",
                "At least a few weeks of completed trip history is required to generate forecasts.",
              )}
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}
