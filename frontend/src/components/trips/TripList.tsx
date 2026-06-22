import { motion } from "framer-motion";
import { ArrowRight, MapPin, Truck, User } from "lucide-react";

import { Trip } from "../../types";
import {
  TRIP_STATUS_IPTAL,
  TRIP_STATUS_PLANLANDI,
  TRIP_STATUS_TAMAMLANDI,
  normalizeTripStatus,
} from "../../lib/trip-status";
import { useTripsResources } from "../../resources/useResources";

interface TripListProps {
  trips: Trip[];
  onSelect: (trip: Trip) => void;
  loading: boolean;
}

const getStatusBadgeClass = (status?: string) => {
  const normalizedStatus = normalizeTripStatus(status);

  if (normalizedStatus === TRIP_STATUS_PLANLANDI) {
    return "bg-warning/10 text-warning";
  }
  if (normalizedStatus === TRIP_STATUS_TAMAMLANDI) {
    return "bg-success/10 text-success";
  }
  if (normalizedStatus === TRIP_STATUS_IPTAL) {
    return "bg-danger/10 text-danger";
  }

  return "bg-elevated text-secondary";
};

export function TripList({ trips, onSelect, loading }: TripListProps) {
  const { tripListText } = useTripsResources();
  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-primary" />
      </div>
    );
  }

  if (trips.length === 0) {
    return (
      <div className="rounded-3xl border border-dashed border-border bg-elevated/20 p-12 text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full border border-border bg-surface shadow-sm">
          <MapPin className="h-8 w-8 text-secondary" />
        </div>
        <h3 className="font-bold text-primary">{tripListText.emptyTitle}</h3>
        <p className="mt-1 text-sm text-secondary">
          {tripListText.emptyDescription}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {trips.map((trip, index) => {
        const normalizedStatus = normalizeTripStatus(trip.durum);
        const displayStatus =
          normalizedStatus ?? trip.durum ?? tripListText.unknownStatus;

        return (
          <motion.div
            key={trip.id}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.05 }}
            onClick={() => onSelect(trip)}
            className="group relative cursor-pointer overflow-hidden rounded-2xl border border-border bg-surface p-5 transition-all hover:border-accent/30 hover:shadow-lg hover:shadow-accent/5"
          >
            <div className="absolute bottom-0 left-0 top-0 w-1.5 bg-elevated transition-colors group-hover:bg-accent" />

            <div className="flex flex-col gap-6 pl-3 md:flex-row md:items-center">
              <div className="min-w-[100px]">
                <span className="mb-1 block text-xs font-mono text-secondary">
                  #{trip.id?.toString().padStart(4, "0")}
                </span>
                <span
                  className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-bold ${getStatusBadgeClass(
                    trip.durum,
                  )}`}
                >
                  {normalizedStatus === TRIP_STATUS_PLANLANDI && (
                    <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-warning" />
                  )}
                  {displayStatus}
                </span>
              </div>

              <div className="flex flex-1 items-center gap-3">
                <div className="text-right">
                  <div className="font-bold text-primary">
                    {trip.cikis_yeri}
                  </div>
                  <div className="text-xs font-medium text-secondary">
                    {new Date(trip.tarih).toLocaleDateString("tr-TR", {
                      day: "numeric",
                      month: "short",
                    })}
                  </div>
                </div>

                <div className="flex min-w-[80px] flex-1 flex-col items-center px-2">
                  <ArrowRight className="h-5 w-5 text-secondary/30" />
                </div>

                <div className="text-left">
                  <div className="font-bold text-primary">
                    {trip.varis_yeri}
                  </div>
                  <div className="text-xs font-medium text-secondary">-</div>
                </div>
              </div>

              <div className="mt-4 flex items-center gap-6 border-t border-border pt-4 md:mt-0 md:border-l md:border-t-0 md:pl-6 md:pt-0">
                <div className="flex items-center gap-2">
                  <Truck className="h-4 w-4 text-secondary" />
                  <div className="text-sm">
                    <div className="font-bold text-primary">
                      {trip.arac_plaka || tripListText.missingPlate}
                    </div>
                    <div className="text-xs text-secondary">
                      {tripListText.vehicleLabel}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <User className="h-4 w-4 text-secondary" />
                  <div className="text-sm">
                    <div className="font-bold text-primary">
                      {trip.sofor_ad_soyad?.split(" ")[0] ||
                        tripListText.missingDriver}
                    </div>
                    <div className="text-xs text-secondary">
                      {tripListText.driverLabel}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
