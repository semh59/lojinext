import { useQuery } from "@tanstack/react-query";

import { AnimatePresence, motion } from "framer-motion";
import {
  Calendar,
  Clock,
  Fuel,
  Gauge,
  Route,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  Truck,
  X,
  Zap,
} from "lucide-react";

import { vehicleService } from "../../api/vehicles";
import { Vehicle, VehicleEvent } from "../../types";
import { useVehiclesResources } from "../../resources/useResources";
interface VehicleDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  vehicle: Vehicle | null;
}

function getInspectionInfo(muayene_tarihi: string | null | undefined) {
  if (!muayene_tarihi) return null;
  const days = Math.ceil(
    (new Date(muayene_tarihi).getTime() - Date.now()) / 86_400_000,
  );
  return { days, date: new Date(muayene_tarihi).toLocaleDateString("tr-TR") };
}

export function VehicleDetailModal({
  isOpen,
  onClose,
  vehicle,
}: VehicleDetailModalProps) {
  const { vehicleDetailText } = useVehiclesResources();
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["vehicle-stats", vehicle?.id],
    queryFn: () => vehicleService.getStats(vehicle!.id!),
    enabled: isOpen && !!vehicle?.id,
    staleTime: 2 * 60 * 1000,
  });

  const { data: events, isLoading: eventsLoading } = useQuery({
    queryKey: ["vehicle-events", vehicle?.id],
    queryFn: () => vehicleService.getEvents(vehicle!.id!),
    enabled: isOpen && !!vehicle?.id,
    staleTime: 2 * 60 * 1000,
  });

  if (!isOpen || !vehicle) {
    return null;
  }

  const inspection = getInspectionInfo(vehicle.muayene_tarihi);
  const currentYear = new Date().getFullYear();
  const vehicleAge = currentYear - vehicle.yil;
  const agingPct = +(vehicleAge * 1.5).toFixed(1);

  let efficiencyPct: number | null = null;
  if (vehicle.hedef_tuketim && stats?.ort_tuketim && stats.ort_tuketim > 0) {
    efficiencyPct =
      ((vehicle.hedef_tuketim - stats.ort_tuketim) / vehicle.hedef_tuketim) *
      100;
  }

  const statCards = [
    {
      icon: <Route className="h-5 w-5" />,
      label: vehicleDetailText.stats.totalTrips,
      value: stats?.toplam_sefer != null ? String(stats.toplam_sefer) : "-",
      color: "text-accent bg-accent/10",
    },
    {
      icon: <Gauge className="h-5 w-5" />,
      label: vehicleDetailText.stats.totalDistance,
      value: stats?.toplam_km
        ? `${stats.toplam_km.toLocaleString("tr-TR")} km`
        : "-",
      color: "text-success bg-success/10",
    },
    {
      icon: <TrendingUp className="h-5 w-5" />,
      label: vehicleDetailText.stats.averageConsumption,
      value: stats?.ort_tuketim
        ? `${Number(stats.ort_tuketim).toFixed(1)} L/100km`
        : "-",
      color: "text-warning bg-warning/10",
    },
    {
      icon: <Fuel className="h-5 w-5" />,
      label: vehicleDetailText.stats.totalFuel,
      value: stats?.toplam_yakit
        ? `${Math.round(stats.toplam_yakit).toLocaleString("tr-TR")} L`
        : "-",
      color: "text-info bg-info/10",
    },
  ];

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[60] flex items-center justify-center bg-base/60 p-4 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          transition={{ duration: 0.2 }}
          className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-modal border border-border bg-surface shadow-lg"
        >
          <div className="relative shrink-0 border-b border-border bg-elevated p-6">
            <button
              onClick={onClose}
              className="absolute right-4 top-4 rounded-full p-2 text-secondary transition-colors hover:bg-surface hover:text-primary"
            >
              <X className="h-5 w-5" />
            </button>

            <div className="flex items-center gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-card border border-border bg-surface shadow-sm">
                <Truck className="h-8 w-8 text-accent" />
              </div>
              <div>
                <h2 className="text-2xl font-bold tracking-tight text-primary">
                  {vehicle.marka} {vehicle.model}
                </h2>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <span className="rounded-lg border border-border bg-surface px-3 py-0.5 font-mono text-lg text-primary">
                    {vehicle.plaka}
                  </span>
                  <span
                    className={`flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-bold ${
                      vehicle.aktif
                        ? "border-success/20 bg-success/10 text-success"
                        : "border-border bg-surface text-secondary"
                    }`}
                  >
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        vehicle.aktif ? "bg-success" : "bg-secondary"
                      }`}
                    />
                    {vehicle.aktif
                      ? vehicleDetailText.status.active
                      : vehicleDetailText.status.inactive}
                  </span>
                  {inspection && inspection.days < 0 && (
                    <span className="flex items-center gap-1 rounded-full border border-danger/30 bg-danger/10 px-2 py-0.5 text-[10px] font-bold text-danger">
                      <ShieldAlert className="h-3 w-3" />
                      {vehicleDetailText.inspection.expiredBadge}
                    </span>
                  )}
                  {inspection &&
                    inspection.days >= 0 &&
                    inspection.days <= 30 && (
                      <span className="flex items-center gap-1 rounded-full border border-warning/30 bg-warning/10 px-2 py-0.5 text-[10px] font-bold text-warning">
                        <ShieldAlert className="h-3 w-3" />
                        {vehicleDetailText.inspection.expiringSoonBadge(
                          inspection.days,
                        )}
                      </span>
                    )}
                </div>
              </div>
            </div>
          </div>

          <div className="custom-scrollbar flex-1 space-y-6 overflow-y-auto p-6">
            {/* Stats grid */}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {statCards.map((stat, index) => (
                <motion.div
                  key={stat.label}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.07 }}
                  className="rounded-card border border-border bg-surface p-4 text-center shadow-sm transition-colors hover:bg-elevated"
                >
                  <div
                    className={`mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-xl ${stat.color}`}
                  >
                    {stat.icon}
                  </div>
                  <p className="text-xs font-medium text-secondary">
                    {stat.label}
                  </p>
                  <p className="mt-0.5 text-lg font-bold text-primary">
                    {statsLoading ? (
                      <span className="inline-block h-5 w-12 animate-pulse rounded bg-border" />
                    ) : (
                      stat.value
                    )}
                  </p>
                </motion.div>
              ))}
            </div>

            {/* Efficiency score */}
            {!statsLoading && efficiencyPct !== null && (
              <div
                className={`rounded-card border p-4 ${
                  efficiencyPct >= 0
                    ? "border-success/30 bg-success/5"
                    : "border-danger/30 bg-danger/5"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Zap
                      className={`h-4 w-4 ${
                        efficiencyPct >= 0 ? "text-success" : "text-danger"
                      }`}
                    />
                    <span className="text-xs font-bold uppercase tracking-widest text-secondary">
                      {vehicleDetailText.efficiency.label}
                    </span>
                  </div>
                  <span
                    className={`text-lg font-black ${
                      efficiencyPct >= 0 ? "text-success" : "text-danger"
                    }`}
                  >
                    {efficiencyPct >= 0
                      ? vehicleDetailText.efficiency.efficient(efficiencyPct)
                      : vehicleDetailText.efficiency.inefficient(
                          Math.abs(efficiencyPct),
                        )}
                  </span>
                </div>
                <div className="mt-2 flex gap-4 text-xs text-secondary">
                  <span>
                    {vehicleDetailText.efficiency.targetLabel}:{" "}
                    {vehicle.hedef_tuketim} L/100km
                  </span>
                  <span>
                    {vehicleDetailText.efficiency.actualLabel}:{" "}
                    {Number(stats!.ort_tuketim).toFixed(1)} L/100km
                  </span>
                </div>
              </div>
            )}

            {/* Aging effect */}
            {vehicleAge >= 8 && (
              <div className="rounded-card border border-warning/20 bg-warning/5 px-4 py-3">
                <p className="text-xs font-bold text-warning">
                  {vehicleDetailText.aging.label(vehicleAge)} —{" "}
                  {vehicleDetailText.aging.degradation(agingPct)}
                </p>
              </div>
            )}

            <div className="space-y-6">
              <div>
                <h3 className="mb-3 text-sm font-bold uppercase tracking-widest text-secondary">
                  {vehicleDetailText.sections.basic}
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <DetailItem
                    icon={<Calendar />}
                    label={vehicleDetailText.fields.productionYear}
                    value={vehicle.yil?.toString()}
                  />
                  <DetailItem
                    icon={<Fuel />}
                    label={vehicleDetailText.fields.tankCapacity}
                    value={
                      vehicle.tank_kapasitesi
                        ? `${vehicle.tank_kapasitesi} L`
                        : "-"
                    }
                  />
                  <DetailItem
                    icon={<TrendingUp />}
                    label={vehicleDetailText.fields.targetConsumption}
                    value={
                      vehicle.hedef_tuketim
                        ? `${vehicle.hedef_tuketim} L/100km`
                        : "-"
                    }
                  />
                  <DetailItem
                    icon={<Gauge />}
                    label={vehicleDetailText.fields.maxPayload}
                    value={
                      vehicle.maks_yuk_kapasitesi_kg
                        ? `${vehicle.maks_yuk_kapasitesi_kg.toLocaleString(
                            "tr-TR",
                          )} kg`
                        : "-"
                    }
                  />
                  <DetailItem
                    icon={
                      vehicle.muayene_tarihi &&
                      getInspectionInfo(vehicle.muayene_tarihi)!.days < 0 ? (
                        <ShieldAlert className="text-danger" />
                      ) : (
                        <ShieldCheck className="text-success" />
                      )
                    }
                    label={vehicleDetailText.fields.inspectionDate}
                    value={inspection?.date ?? "-"}
                  />
                </div>
              </div>

              {(vehicle.bos_agirlik_kg ||
                vehicle.hava_direnc_katsayisi ||
                vehicle.motor_verimliligi) && (
                <div>
                  <h3 className="mb-3 text-sm font-bold uppercase tracking-widest text-secondary">
                    {vehicleDetailText.sections.physics}
                  </h3>
                  <div className="grid grid-cols-3 gap-3">
                    <MiniStat
                      label={vehicleDetailText.fields.emptyWeight}
                      value={
                        vehicle.bos_agirlik_kg
                          ? `${vehicle.bos_agirlik_kg.toLocaleString(
                              "tr-TR",
                            )} kg`
                          : "-"
                      }
                    />
                    <MiniStat
                      label={vehicleDetailText.fields.dragCoefficient}
                      value={vehicle.hava_direnc_katsayisi?.toString() ?? "-"}
                    />
                    <MiniStat
                      label={vehicleDetailText.fields.frontalArea}
                      value={
                        vehicle.on_kesit_alani_m2
                          ? `${vehicle.on_kesit_alani_m2} m²`
                          : "-"
                      }
                    />
                    <MiniStat
                      label={vehicleDetailText.fields.engineEfficiency}
                      value={
                        vehicle.motor_verimliligi
                          ? `%${(vehicle.motor_verimliligi * 100).toFixed(0)}`
                          : "-"
                      }
                    />
                    <MiniStat
                      label={vehicleDetailText.fields.rollingResistance}
                      value={vehicle.lastik_direnc_katsayisi?.toString() ?? "-"}
                    />
                  </div>
                </div>
              )}

              {vehicle.notlar && (
                <div>
                  <h3 className="mb-2 text-sm font-bold uppercase tracking-widest text-secondary">
                    {vehicleDetailText.sections.notes}
                  </h3>
                  <p className="rounded-xl border border-border bg-surface p-4 text-sm text-primary">
                    {vehicle.notlar}
                  </p>
                </div>
              )}

              {/* Events timeline */}
              <div>
                <h3 className="mb-3 text-sm font-bold uppercase tracking-widest text-secondary">
                  {vehicleDetailText.sections.events}
                </h3>
                {eventsLoading ? (
                  <div className="space-y-2">
                    {[1, 2, 3].map((i) => (
                      <div
                        key={i}
                        className="h-12 animate-pulse rounded-card border border-border bg-elevated"
                      />
                    ))}
                  </div>
                ) : events && events.length > 0 ? (
                  <div className="space-y-2">
                    {events.map((event: VehicleEvent) => (
                      <EventRow key={event.id} event={event} />
                    ))}
                  </div>
                ) : (
                  <p className="rounded-card border border-border bg-elevated px-4 py-3 text-sm text-secondary">
                    {vehicleDetailText.events.noEvents}
                  </p>
                )}
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}

function EventRow({ event }: { event: VehicleEvent }) {
  const { vehicleDetailText } = useVehiclesResources();
  const formatted = event.created_at
    ? new Date(event.created_at).toLocaleString("tr-TR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

  return (
    <div className="flex items-start gap-3 rounded-card border border-border bg-elevated px-4 py-3">
      <Clock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent/60" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-bold text-primary">
          {vehicleDetailText.events.types[event.event_type] ?? event.event_type}
          {event.triggered_by && (
            <span className="ml-1 font-normal text-secondary text-xs">
              {vehicleDetailText.events.by(event.triggered_by)}
            </span>
          )}
        </p>
        {event.details && (
          <p className="mt-0.5 truncate text-xs text-secondary">
            {event.details}
          </p>
        )}
      </div>
      {formatted && (
        <span className="shrink-0 text-[10px] text-tertiary">{formatted}</span>
      )}
    </div>
  );
}

function DetailItem({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value?: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-surface p-3 shadow-sm transition-colors hover:bg-elevated">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-elevated text-accent shadow-sm">
        {icon}
      </div>
      <div>
        <p className="text-xs text-secondary">{label}</p>
        <p className="font-semibold text-primary">{value || "-"}</p>
      </div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-3 text-center shadow-sm transition-colors hover:bg-elevated">
      <p className="text-xs text-secondary">{label}</p>
      <p className="mt-0.5 font-bold text-primary">{value}</p>
    </div>
  );
}
