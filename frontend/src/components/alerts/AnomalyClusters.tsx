import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { anomalyService } from "../../api/anomalies";

export function AnomalyClusters() {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: ["anomalyClusters", 30],
    queryFn: () => anomalyService.getClusters(30),
  });

  if (isLoading)
    return (
      <p className="text-sm text-tertiary">
        {t("alerts.clusters_calculating")}
      </p>
    );

  const clusters = data?.clusters ?? [];
  if (clusters.length === 0)
    return (
      <p className="text-sm text-tertiary">
        {t("alerts.clusters_none", { days: data?.period_days ?? 30 })}
      </p>
    );

  return (
    <div className="space-y-3">
      {clusters.map((c) => (
        <div
          key={c.cluster_id}
          className="rounded-card border border-border bg-surface p-3"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-semibold text-primary">
              {c.label}
            </span>
            <span className="text-xs text-tertiary">
              {t("alerts.clusters_count", { n: c.size })}
            </span>
          </div>
          {c.insight && (
            <p className="mt-1 text-xs text-secondary">{c.insight}</p>
          )}
        </div>
      ))}
    </div>
  );
}

export default AnomalyClusters;
