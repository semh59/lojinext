import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertCircle, Loader2, Trophy, Info } from "lucide-react";
import { chartTheme } from "../../lib/chart-theme";
import {
  driverService,
  type DriverRouteProfile as RouteProfileData,
} from "../../api/drivers";
import { useTranslation } from "react-i18next";

interface DriverRouteProfileProps {
  driverId: number;
}

function findBestLabel(data: RouteProfileData): string | null {
  if (!data.best_route_type) return null;
  const best = data.profiles.find((p) => p.route_type === data.best_route_type);
  return best?.label ?? null;
}

export function DriverRouteProfile({ driverId }: DriverRouteProfileProps) {
  const { t } = useTranslation();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["driverRouteProfile", driverId],
    queryFn: () => driverService.getRouteProfile(driverId),
    staleTime: 10 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-3 py-12 text-secondary">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span className="text-sm">{t("drivers.route_profile_loading")}</span>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex items-center justify-center gap-3 py-12 text-danger">
        <AlertCircle className="h-5 w-5" />
        <span className="text-sm">{t("drivers.route_profile_error")}</span>
      </div>
    );
  }

  const hasAnyTrip = data.profiles.some((p) => p.trip_count > 0);
  const bestLabel = findBestLabel(data);
  // Chart için sadece veri olan tipleri sırala
  const chartData = data.profiles.map((p) => ({
    ...p,
    // bar rengi sapma yönüne göre — pozitif (kötü) kırmızı, negatif (iyi) yeşil
    barColor:
      p.trip_count === 0
        ? chartTheme.colors.border
        : p.deviation_pct < -2
          ? chartTheme.colors.success
          : p.deviation_pct > 2
            ? chartTheme.colors.danger
            : chartTheme.colors.warning,
  }));

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-2 rounded-card border border-info/20 bg-info/5 px-4 py-3">
        <Info className="h-4 w-4 shrink-0 text-info mt-0.5" />
        <p className="text-xs leading-relaxed text-secondary">
          {t("drivers.route_profile_description", {
            n: data.min_trips_for_best,
          })}
        </p>
      </div>

      {bestLabel ? (
        <div className="flex items-center gap-3 rounded-modal border border-success/20 bg-success/5 px-4 py-3">
          <Trophy className="h-5 w-5 text-success" />
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-secondary">
              {t("drivers.route_best_type")}
            </p>
            <p className="text-sm font-semibold text-primary">{bestLabel}</p>
          </div>
        </div>
      ) : (
        <div className="rounded-card border border-warning/20 bg-warning/5 px-4 py-3">
          <p className="text-xs text-secondary">
            {t("drivers.route_no_best", { n: data.min_trips_for_best })}
          </p>
        </div>
      )}

      {hasAnyTrip ? (
        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              margin={{ top: 8, right: 12, left: -10, bottom: 0 }}
            >
              <CartesianGrid {...chartTheme.grid} />
              <XAxis
                dataKey="label"
                tick={chartTheme.tickSmall}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={chartTheme.tick}
                unit=" %"
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                {...chartTheme.tooltip}
                formatter={(value, _name, payload) => {
                  const num = Number(value ?? 0);
                  const item = (payload as any)?.payload as
                    | RouteProfileData["profiles"][number]
                    | undefined;
                  if (!item)
                    return [
                      `${num.toFixed(1)}%`,
                      t("drivers.route_tooltip_deviation"),
                    ];
                  return [
                    `${num.toFixed(1)}% (${t("drivers.route_trip_count", {
                      n: item.trip_count,
                    })})`,
                    item.label,
                  ];
                }}
              />
              <Bar dataKey="deviation_pct" radius={[6, 6, 0, 0]}>
                {chartData.map((entry) => (
                  <Cell key={entry.route_type} fill={entry.barColor} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="text-sm text-secondary text-center py-6">
          {t("drivers.route_no_trips")}
        </p>
      )}

      <div className="space-y-2">
        {data.profiles.map((p) => (
          <div
            key={p.route_type}
            className="flex items-baseline justify-between gap-3 rounded-card bg-elevated/30 px-3 py-2"
          >
            <span className="text-xs font-semibold text-primary">
              {p.label}
            </span>
            <div className="font-mono tabular-nums text-xs text-secondary flex items-center gap-3">
              <span>{t("drivers.route_trip_count", { n: p.trip_count })}</span>
              {p.trip_count > 0 ? (
                <>
                  <span>
                    {p.avg_actual.toFixed(1)} / {p.avg_predicted.toFixed(1)} L
                  </span>
                  <span
                    className={
                      p.deviation_pct < -2
                        ? "text-success font-semibold"
                        : p.deviation_pct > 2
                          ? "text-danger font-semibold"
                          : "text-warning"
                    }
                  >
                    {p.deviation_pct > 0 ? "+" : ""}
                    {p.deviation_pct.toFixed(1)}%
                  </span>
                </>
              ) : (
                <span className="text-tertiary">—</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
