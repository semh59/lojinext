import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: ["pageViewStats", 30],
    queryFn: () => fetchPageViewStats(30),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-primary">
          {t("admin.analytics_title", "Usage Analytics")}
        </h1>
        <span className="text-sm text-tertiary">
          {t(
            "admin.analytics_period",
            "Last {{n}} days — {{total}} total views",
            {
              n: data?.period_days ?? 30,
              total: data?.total_views ?? 0,
            },
          )}
        </span>
      </div>
      {isLoading ? (
        <p className="text-sm text-tertiary">
          {t("admin.analytics_loading", "Loading…")}
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <RouteList
            title={t("admin.analytics_top_routes", "Most used")}
            rows={data?.top_routes ?? []}
          />
          <RouteList
            title={t("admin.analytics_bottom_routes", "Least used")}
            rows={data?.bottom_routes ?? []}
          />
        </div>
      )}
    </div>
  );
}
