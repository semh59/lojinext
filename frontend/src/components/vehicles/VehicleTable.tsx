import { useEffect, useState } from "react";

import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  Calendar,
  Droplet,
  Edit2,
  Gauge,
  ShieldAlert,
  Trash2,
  Truck,
} from "lucide-react";

import { Vehicle } from "../../types";
import { cn } from "../../lib/utils";
import { Badge } from "../ui/Badge";
import { SkeletonTable } from "./SkeletonTable";
import { useVehiclesResources } from "../../resources/useResources";

interface VehicleTableProps {
  vehicles: Vehicle[];
  loading: boolean;
  onEdit: (vehicle: Vehicle) => void;
  onDelete: (vehicle: Vehicle) => void | Promise<void>;
  onViewDetail: (vehicle: Vehicle) => void;
}

export function VehicleTable({
  vehicles,
  loading,
  onEdit,
  onDelete,
  onViewDetail,
}: VehicleTableProps) {
  const { vehicleTableText, vehicleCardText } = useVehiclesResources();
  function getInspectionStatus(muayene_tarihi: string | null | undefined): {
    type: "expired" | "expiring" | "ok" | "unknown";
    daysLeft: number;
    label: string;
  } {
    if (!muayene_tarihi) return { type: "unknown", daysLeft: 0, label: "" };
    const days = Math.ceil(
      (new Date(muayene_tarihi).getTime() - Date.now()) / 86_400_000,
    );
    if (days < 0)
      return {
        type: "expired",
        daysLeft: days,
        label: vehicleCardText.inspection.expired,
      };
    if (days <= 30)
      return {
        type: "expiring",
        daysLeft: days,
        label: vehicleCardText.inspection.expiringSoon(days),
      };
    return { type: "ok", daysLeft: days, label: "" };
  }
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set());
  const [deletedIds, setDeletedIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    setDeletedIds(new Set());
    setDeletingIds(new Set());
  }, [vehicles]);

  const handleOptimisticDelete = async (vehicle: Vehicle) => {
    if (!vehicle.id) {
      return;
    }

    const id = vehicle.id;
    setDeletedIds((previous) => new Set([...previous, id]));
    setDeletingIds((previous) => new Set([...previous, id]));

    try {
      await onDelete(vehicle);
    } catch {
      setDeletedIds((previous) => {
        const next = new Set(previous);
        next.delete(id);
        return next;
      });
    } finally {
      setDeletingIds((previous) => {
        const next = new Set(previous);
        next.delete(id);
        return next;
      });
    }
  };

  if (loading) {
    return <SkeletonTable rows={5} />;
  }

  if (vehicles.length === 0) {
    return (
      <div className="group flex flex-col items-center justify-center rounded-modal border border-border border-dashed bg-elevated p-16 text-center">
        <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-card border border-border bg-surface shadow-sm transition-transform duration-300 group-hover:scale-105">
          <Truck className="h-10 w-10 text-secondary" />
        </div>
        <h3 className="mb-2 text-xl font-bold tracking-tight text-primary">
          {vehicleTableText.emptyTitle}
        </h3>
        <p className="max-w-sm text-sm font-medium text-secondary">
          {vehicleTableText.emptyDescription}
        </p>
      </div>
    );
  }

  const visibleVehicleCount = vehicles.filter(
    (vehicle) => !deletedIds.has(vehicle.id!),
  ).length;

  return (
    <div className="w-full space-y-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-3 text-[18px] font-bold tracking-tight text-primary">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-surface text-accent shadow-sm">
            <Truck className="h-5 w-5" />
          </div>
          {vehicleTableText.title}
        </h2>
        <div className="rounded-xl border border-border bg-surface px-4 py-2 text-sm font-bold text-secondary shadow-sm">
          <span className="ml-1 text-accent">
            {vehicleTableText.totalCount(visibleVehicleCount)}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <AnimatePresence>
          {vehicles
            .filter((vehicle) => vehicle.id && !deletedIds.has(vehicle.id))
            .map((vehicle, index) => {
              const inspection = getInspectionStatus(vehicle.muayene_tarihi);
              const currentYear = new Date().getFullYear();
              const vehicleAge = currentYear - vehicle.yil;
              const agingPct = +(vehicleAge * 1.5).toFixed(1);

              return (
                <motion.div
                  key={vehicle.id}
                  initial={{ opacity: 0, scale: 0.95, y: 20 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.9, y: -20 }}
                  transition={{ duration: 0.3, delay: index * 0.05 }}
                  className={cn(
                    "group relative flex flex-col overflow-hidden rounded-modal border border-border bg-surface p-6 shadow-sm transition-all hover:-translate-y-1 hover:border-accent hover:shadow",
                    vehicle.id &&
                      deletingIds.has(vehicle.id) &&
                      "pointer-events-none opacity-50 grayscale",
                  )}
                >
                  <div className="absolute right-0 top-0 h-32 w-32 -translate-y-1/2 translate-x-1/2 rounded-full bg-accent/10 blur-[40px] opacity-0 transition-opacity duration-500 group-hover:opacity-100" />

                  {/* Status + inspection badges */}
                  <div className="absolute right-6 top-6 z-10 flex flex-col items-end gap-1.5">
                    <Badge
                      variant={vehicle.aktif ? "success" : "default"}
                      pulse={vehicle.aktif}
                      className="text-[10px] uppercase tracking-widest"
                    >
                      {vehicle.aktif
                        ? vehicleTableText.status.active
                        : vehicleTableText.status.inactive}
                    </Badge>
                    {inspection.type === "expired" && (
                      <span className="flex items-center gap-1 rounded-full border border-danger/30 bg-danger/10 px-2 py-0.5 text-[9px] font-black uppercase tracking-widest text-danger">
                        <ShieldAlert className="h-2.5 w-2.5" />
                        {inspection.label}
                      </span>
                    )}
                    {inspection.type === "expiring" && (
                      <span className="flex items-center gap-1 rounded-full border border-warning/30 bg-warning/10 px-2 py-0.5 text-[9px] font-black uppercase tracking-widest text-warning">
                        <AlertTriangle className="h-2.5 w-2.5" />
                        {inspection.label}
                      </span>
                    )}
                  </div>

                  <div className="relative z-10 mb-6 flex items-start gap-4">
                    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-[16px] border border-border bg-elevated">
                      <Truck className="h-7 w-7 text-secondary" />
                    </div>
                    <div className="min-w-0 flex-1 pr-20">
                      <div className="mb-2 inline-flex items-center rounded border border-border bg-elevated px-2.5 py-1 text-[11px] font-bold tracking-widest text-primary shadow-sm">
                        {vehicle.plaka}
                      </div>
                      <h3 className="truncate text-[16px] font-bold tracking-tight text-primary transition-colors group-hover:text-accent">
                        {vehicle.marka} {vehicle.model}
                      </h3>
                    </div>
                  </div>

                  <div className="relative z-10 mb-6 grid grid-cols-2 gap-3">
                    <div className="flex flex-col gap-1 rounded-card border border-border bg-elevated p-3">
                      <div className="mb-0.5 flex items-center gap-1.5 text-secondary">
                        <Calendar className="h-3.5 w-3.5" />
                        <span className="text-[10px] font-bold uppercase tracking-wider">
                          {vehicleTableText.labels.modelYear}
                        </span>
                      </div>
                      <span className="text-[14px] font-bold text-primary">
                        {vehicle.yil}
                      </span>
                      {vehicleAge >= 8 && (
                        <span className="text-[9px] font-bold text-warning/70 uppercase tracking-wider">
                          -{agingPct}% etki
                        </span>
                      )}
                    </div>
                    <div className="flex flex-col gap-1 rounded-card border border-border bg-elevated p-3">
                      <div className="mb-0.5 flex items-center gap-1.5 text-secondary">
                        <Droplet className="h-3.5 w-3.5" />
                        <span className="text-[10px] font-bold uppercase tracking-wider">
                          {vehicleTableText.labels.fuelCapacity}
                        </span>
                      </div>
                      <span className="text-[14px] font-bold text-primary">
                        {vehicle.tank_kapasitesi?.toLocaleString("tr-TR") ||
                          "-"}{" "}
                        L
                      </span>
                    </div>
                    <div className="col-span-2 flex flex-col gap-1 rounded-card border border-border bg-elevated p-3">
                      <div className="mb-0.5 flex items-center gap-1.5 text-secondary">
                        <Gauge className="h-3.5 w-3.5" />
                        <span className="text-[10px] font-bold uppercase tracking-wider">
                          {vehicleTableText.labels.targetConsumption}
                        </span>
                      </div>
                      <span className="text-[14px] font-bold text-primary">
                        {vehicle.hedef_tuketim || "-"} L/100km
                      </span>
                    </div>
                  </div>

                  <div className="flex-1" />

                  <div className="relative z-10 flex items-center justify-between border-t border-border pt-4">
                    <button
                      onClick={() => onViewDetail(vehicle)}
                      className="flex h-10 items-center gap-2 rounded-card border border-accent/20 bg-accent/10 px-4 text-xs font-bold text-accent transition-all hover:border-accent/40 hover:bg-accent/20"
                    >
                      <Activity className="h-4 w-4" />
                      {vehicleTableText.actions.insights}
                    </button>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => onEdit(vehicle)}
                        className="flex h-10 w-10 items-center justify-center rounded-card border border-border bg-surface text-secondary transition-all hover:bg-elevated hover:text-accent"
                        title={vehicleTableText.actions.edit}
                      >
                        <Edit2 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() =>
                          vehicle.id && handleOptimisticDelete(vehicle)
                        }
                        disabled={!!vehicle.id && deletingIds.has(vehicle.id)}
                        className="flex h-10 w-10 items-center justify-center rounded-card border border-danger/20 bg-danger/10 text-danger transition-all hover:border-danger/40 hover:bg-danger/20 disabled:opacity-50"
                        title={vehicleTableText.actions.delete}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </motion.div>
              );
            })}
        </AnimatePresence>
      </div>
    </div>
  );
}
