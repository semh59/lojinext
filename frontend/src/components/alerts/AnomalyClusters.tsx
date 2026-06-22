import { useQuery } from "@tanstack/react-query";
import { anomalyService } from "../../api/anomalies";

/**
 * Faz 8 — anomali kümeleri (tekrarlayan desenler). DBSCAN ile backend'de
 * hesaplanır; opsiyonel Groq insight metni gösterilir.
 */
export function AnomalyClusters() {
  const { data, isLoading } = useQuery({
    queryKey: ["anomalyClusters", 30],
    queryFn: () => anomalyService.getClusters(30),
  });

  if (isLoading)
    return <p className="text-sm text-tertiary">Kümeler hesaplanıyor…</p>;

  const clusters = data?.clusters ?? [];
  if (clusters.length === 0)
    return (
      <p className="text-sm text-tertiary">
        Son {data?.period_days ?? 30} günde anlamlı bir anomali deseni yok.
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
            <span className="text-xs text-tertiary">{c.size} anomali</span>
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
