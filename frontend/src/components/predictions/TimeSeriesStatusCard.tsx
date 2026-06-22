import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/Card";
import { Activity, CheckCircle2, AlertTriangle } from "lucide-react";
import { predictionService } from "@/api/predictions";

export function TimeSeriesStatusCard() {
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
          Zaman Serisi Modeli
        </h2>
      </div>

      {isLoading ? (
        <div className="h-10 animate-pulse rounded-card bg-elevated/40" />
      ) : isAvailable ? (
        <div className="flex items-center gap-3 rounded-card border border-success/20 bg-success/5 px-4 py-3">
          <CheckCircle2 className="h-5 w-5 text-success" />
          <div>
            <p className="text-sm font-semibold text-primary">Hazır</p>
            <p className="text-[11px] text-secondary">
              Yöntem: <span className="font-mono">{method}</span>
              {typeof historyDays === "number" &&
                ` · ${historyDays} günlük geçmiş`}
            </p>
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-3 rounded-card border border-warning/20 bg-warning/5 px-4 py-3">
          <AlertTriangle className="h-5 w-5 text-warning" />
          <div>
            <p className="text-sm font-semibold text-primary">
              Yeterli veri yok
            </p>
            <p className="text-[11px] text-secondary">
              Tahmin oluşturmak için en az birkaç haftalık tamamlanmış sefer
              geçmişi gerekir.
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}
