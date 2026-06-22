import { useQuery } from "@tanstack/react-query";
import { fetchPageViewStats } from "../../api/analytics";

function RouteList({
  title,
  rows,
}: {
  title: string;
  rows: { route: string; count: number }[];
}) {
  return (
    <div className="rounded-modal border border-border bg-surface p-4">
      <h3 className="mb-2 text-sm font-semibold text-secondary">{title}</h3>
      <ul className="space-y-1">
        {rows.map((r) => (
          <li
            key={r.route}
            className="flex justify-between text-sm text-primary"
          >
            <span className="font-mono">{r.route}</span>
            <span className="text-tertiary">{r.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function AnalyticsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["pageViewStats", 30],
    queryFn: () => fetchPageViewStats(30),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-primary">Kullanım Analitiği</h1>
        <span className="text-sm text-tertiary">
          Son {data?.period_days ?? 30} gün — toplam {data?.total_views ?? 0}{" "}
          görüntüleme
        </span>
      </div>
      {isLoading ? (
        <p className="text-sm text-tertiary">Yükleniyor…</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <RouteList title="En çok kullanılan" rows={data?.top_routes ?? []} />
          <RouteList
            title="En az kullanılan"
            rows={data?.bottom_routes ?? []}
          />
        </div>
      )}
    </div>
  );
}
