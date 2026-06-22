import { AlertTriangle, Wrench } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import type { FleetInsightsData } from "@/api/anomalies";
import { useLocale } from "../../hooks/useLocale";

interface Props {
  data: FleetInsightsData | undefined;
  isLoading?: boolean;
}

export function AnomalyWidget({ data, isLoading }: Props) {
  const { t } = useTranslation();
  const locale = useLocale();
  return (
    <Card padding="lg" className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-warning" />
        <h2 className="text-sm font-semibold text-primary">
          {t("dashboard.fleet_alerts")}
        </h2>
      </div>
      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-10 animate-pulse rounded-lg bg-elevated/50"
            />
          ))}
        </div>
      ) : !data ? (
        <p className="text-sm text-secondary">{t("dashboard.data_error")}</p>
      ) : (
        <>
          {data.leakage.fuel_gap_liters > 0 ? (
            <div className="rounded-card border border-warning/20 bg-warning/5 px-4 py-3 space-y-1">
              <p className="text-xs font-bold uppercase tracking-wider text-warning">
                {t("alerts.fuel_leak")}
              </p>
              <p className="text-sm text-primary">
                <span className="font-semibold">
                  {data.leakage.fuel_gap_liters.toLocaleString(locale, {
                    maximumFractionDigits: 0,
                  })}{" "}
                  L
                </span>
                {data.leakage.route_deviation_km > 0 && (
                  <span className="text-secondary ml-2">
                    {t("alerts.km_deviation_detail", {
                      km: data.leakage.route_deviation_km.toFixed(0),
                    })}
                  </span>
                )}
              </p>
              <p className="text-xs text-warning/80">
                ≈{" "}
                {data.leakage.fuel_gap_cost.toLocaleString(locale, {
                  style: "currency",
                  currency: "TRY",
                  maximumFractionDigits: 0,
                })}{" "}
                {t("alerts.estimated_loss")}
              </p>
            </div>
          ) : (
            <div className="rounded-card border border-success/20 bg-success/5 px-4 py-3">
              <p className="text-xs font-bold uppercase tracking-wider text-success">
                {t("alerts.fuel_leak")}
              </p>
              <p className="text-sm text-secondary mt-0.5">
                {t("alerts.no_abnormal")}
              </p>
            </div>
          )}

          {data.maintenance.vehicles.length > 0 ? (
            <div className="space-y-2">
              <div className="flex items-center gap-1.5">
                <Wrench className="h-3.5 w-3.5 text-info" />
                <p className="text-xs font-bold uppercase tracking-wider text-secondary">
                  {t("alerts.maintenance_badge", {
                    urgent: data.maintenance.urgent_count,
                    warning: data.maintenance.warning_count,
                  })}
                </p>
              </div>
              {data.maintenance.vehicles.slice(0, 4).map((v) => (
                <div
                  key={v.id}
                  className="flex items-center justify-between rounded-lg border border-border/50 bg-elevated/30 px-3 py-2"
                >
                  <span className="text-sm font-medium text-primary">
                    {v.plaka}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-secondary truncate max-w-[120px]">
                      {v.reason}
                    </span>
                    <Badge
                      variant={v.severity === "high" ? "danger" : "warning"}
                    >
                      {v.severity === "high"
                        ? t("alerts.acil")
                        : t("alerts.uyari")}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-success/20 bg-success/5 px-4 py-3">
              <p className="text-xs font-bold uppercase tracking-wider text-success">
                {t("alerts.maintenance_title")}
              </p>
              <p className="text-sm text-secondary mt-0.5">
                {t("alerts.no_maintenance_vehicles")}
              </p>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
