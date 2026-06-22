import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Route as RouteIcon, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { tripService } from "@/api/trips";
import type { StatusMeta } from "@/lib/status-labels";

// normalizeTripStatus hâlâ Türkçe döndürdüğü için bu harita burada yaşar.
// TripStatus İngilizce'ye migrasyon yapıldığında getTripStatusMeta() ile değişir.
const TURKISH_STATUS_META: Record<string, StatusMeta> = {
  Planlandı: { label: "Planlandı", variant: "info" },
  Yolda: { label: "Yolda", variant: "warning" },
  Tamamlandı: { label: "Tamamlandı", variant: "success" },
  İptal: { label: "İptal", variant: "danger" },
};

export function TodaysActiveTrips() {
  const { t } = useTranslation();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["trips", "today"],
    queryFn: () => tripService.getTodayTrips(),
    staleTime: 60 * 1000,
    refetchOnWindowFocus: true,
  });

  // ISO YYYY-MM-DD; TripsPage useUrlState'in `start`/`end` paramlarına filter olarak gider.
  const todayIso = new Date().toISOString().slice(0, 10);
  const tripsLinkHref = `/trips?baslangic_tarih=${todayIso}&bitis_tarih=${todayIso}`;

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const visible = items.slice(0, 5);

  return (
    <Card padding="lg" className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <RouteIcon className="h-4 w-4 text-accent" />
          <h2 className="text-sm font-semibold text-primary">
            {t("dashboard.todays_trips", "Today's Trips")}
          </h2>
          {total > 0 && (
            <span className="text-xs font-semibold text-secondary">
              ({total})
            </span>
          )}
        </div>
        {total > 5 && (
          <Link
            to={tripsLinkHref}
            className="inline-flex items-center gap-0.5 text-xs font-medium text-accent hover:underline"
          >
            {t("common.see_all", "See All")}{" "}
            <ChevronRight className="h-3 w-3" />
          </Link>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-10 animate-pulse rounded-card bg-elevated/50"
            />
          ))}
        </div>
      ) : isError ? (
        <p className="text-sm text-secondary">
          {t("dashboard.todays_trips_error", "Could not load today's trips")}
        </p>
      ) : visible.length === 0 ? (
        <p className="text-sm text-secondary">
          {t("dashboard.todays_trips_empty", "No trips planned for today")}
        </p>
      ) : (
        <ul className="space-y-2">
          {visible.map((trip) => {
            const durum = trip.durum ?? "Planlandı";
            const meta = TURKISH_STATUS_META[durum] ?? {
              label: durum,
              variant: "neutral" as const,
            };
            return (
              <li
                key={trip.id}
                className="flex items-center justify-between rounded-card border border-border/50 bg-elevated/30 px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-primary">
                    {trip.cikis_yeri} → {trip.varis_yeri}
                  </p>
                  <p className="text-[11px] text-secondary">
                    {trip.sefer_no ?? `#${trip.id}`}
                    {trip.mesafe_km ? ` · ${trip.mesafe_km.toFixed(0)} km` : ""}
                  </p>
                </div>
                <StatusBadge meta={meta} />
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
