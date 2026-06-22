import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { motion } from "framer-motion";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  AlertTriangle,
  ArrowLeftRight,
  Calculator,
  Calendar,
  Check,
  CheckCircle,
  CheckCircle2,
  ChevronRight,
  Clock,
  Droplet,
  Edit2,
  Layers,
  MoreVertical,
  PackageOpen,
  RefreshCw,
  Route,
  Settings,
  Timer,
  Trash2,
  XCircle,
} from "lucide-react";

import { getTripStatusMeta } from "../../lib/status-labels";
import { useLocale } from "../../hooks/useLocale";
import { Trip } from "../../types";
import { cn } from "../../lib/utils";
import { Button } from "../ui/Button";
import { Skeleton } from "../ui/Skeleton";
import {
  TRIP_STATUS_IPTAL,
  TRIP_STATUS_PLANLANDI,
  TRIP_STATUS_TAMAMLANDI,
  normalizeTripStatus,
} from "../../lib/trip-status";
import { useTripsResources } from "../../resources/useResources";

export interface TripTableProps {
  trips: Trip[];
  isLoading: boolean;
  onEdit: (trip: Trip) => void;
  onDelete: (trip: Trip) => void;
  onCreateReturn?: (trip: Trip) => void;
  onStatusChange?: (trip: Trip) => void;
  onOnayla?: (trip: Trip) => void;
  onReddet?: (trip: Trip) => void;
  onCostAnalysis?: (trip: Trip) => void;
  selectedIds?: number[];
  onToggleSelection?: (id: number) => void;
  onViewDetails?: (trip: Trip) => void;
  hasActiveFilter?: boolean;
  onClearFilters?: () => void;
}

const getStatusStyles = (status?: string) => {
  switch (normalizeTripStatus(status)) {
    case TRIP_STATUS_TAMAMLANDI:
      return {
        bg: "bg-success/10",
        text: "text-success",
        border: "border-success/20",
        bar: "bg-success",
        glow: "shadow-success/20",
        icon: <CheckCircle2 size={12} className="mr-1.5" />,
      };
    case TRIP_STATUS_PLANLANDI:
      return {
        bg: "bg-warning/10",
        text: "text-warning",
        border: "border-warning/20",
        bar: "bg-warning",
        glow: "",
        icon: <Timer size={12} className="mr-1.5" />,
      };
    case TRIP_STATUS_IPTAL:
      return {
        bg: "bg-danger/10",
        text: "text-danger",
        border: "border-danger/20",
        bar: "bg-danger",
        glow: "",
        icon: <XCircle size={12} className="mr-1.5" />,
      };
    default:
      return {
        bg: "bg-elevated/50",
        text: "text-secondary",
        border: "border-border/40",
        bar: "bg-secondary",
        glow: "",
        icon: <Clock size={12} className="mr-1.5" />,
      };
  }
};

export function TripTable({
  trips,
  isLoading,
  onEdit,
  onDelete,
  onCreateReturn,
  onStatusChange,
  onOnayla,
  onReddet,
  onCostAnalysis,
  selectedIds = [],
  onToggleSelection,
  onViewDetails,
  hasActiveFilter = false,
  onClearFilters,
}: TripTableProps) {
  const { tripTableText } = useTripsResources();
  const locale = useLocale();
  const getStatusConfig = (status?: string) => {
    switch (normalizeTripStatus(status)) {
      case TRIP_STATUS_TAMAMLANDI:
        return {
          text: getTripStatusMeta("Completed", locale).label,
          progress: 100,
        };
      case TRIP_STATUS_PLANLANDI:
        return {
          text: getTripStatusMeta("Planned", locale).label,
          progress: 35,
        };
      case TRIP_STATUS_IPTAL:
        return {
          text: getTripStatusMeta("Cancelled", locale).label,
          progress: 0,
        };
      default:
        return {
          text: status?.toUpperCase() || tripTableText.unknownValue,
          progress: 0,
        };
    }
  };
  const { hasPermission } = useAuth();
  const canApprove = hasPermission("sefer:onayla");
  const canWrite = hasPermission("sefer:write");

  const parentRef = useRef<HTMLDivElement>(null);

  // Row dropdown click-toggle state. CSS group-hover Playwright headless
  // ortamda fail oluyordu (#157); JS state ile hem hover hem click açma
  // sağlanır. Aynı anda tek menü açık (basit single-state).
  const [openMenuTripId, setOpenMenuTripId] = useState<number | null>(null);
  const menuWrapRef = useRef<HTMLDivElement>(null);

  // Click outside → menüyü kapat (menu içeriği menuWrapRef altında)
  useEffect(() => {
    if (openMenuTripId === null) return;
    const onDocClick = (e: MouseEvent) => {
      if (!menuWrapRef.current) return;
      if (!menuWrapRef.current.contains(e.target as Node)) {
        setOpenMenuTripId(null);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [openMenuTripId]);

  const rowVirtualizer = useVirtualizer({
    count: trips.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 140,
    overscan: 5,
  });

  if (isLoading) {
    return (
      <div className="mt-8 flex flex-col gap-4 animate-pulse">
        {[1, 2, 3, 4, 5].map((index) => (
          <div
            key={index}
            className="flex gap-6 rounded-modal border border-border/40 bg-elevated p-6"
          >
            <Skeleton className="h-full w-1.5 shrink-0 rounded-full" />
            <div className="flex-1 space-y-4">
              <div className="flex justify-between">
                <Skeleton className="h-6 w-1/3" />
                <Skeleton className="h-6 w-24 rounded-full" />
              </div>
              <div className="grid grid-cols-3 gap-6">
                <Skeleton className="h-12 rounded-xl" />
                <Skeleton className="h-12 rounded-xl" />
                <Skeleton className="h-12 rounded-xl" />
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (trips.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="group flex flex-col items-center justify-center rounded-modal border border-dashed border-border/60 bg-elevated py-32"
      >
        <div className="mb-8 flex h-24 w-24 items-center justify-center rounded-full bg-accent/5 text-accent/30 transition-all duration-500 group-hover:scale-110 group-hover:bg-accent/10">
          <PackageOpen size={48} strokeWidth={1.5} />
        </div>
        <h3 className="mb-3 text-2xl font-black uppercase tracking-tight text-primary">
          {hasActiveFilter
            ? tripTableText.filteredEmptyTitle
            : tripTableText.emptyTitle}
        </h3>
        <p className="max-w-xs text-center text-sm font-medium leading-relaxed text-secondary">
          {hasActiveFilter
            ? tripTableText.filteredEmptyDescription
            : tripTableText.emptyDescription}
        </p>
        {hasActiveFilter && onClearFilters && (
          <Button
            variant="secondary"
            onClick={onClearFilters}
            className="mt-8 h-12 rounded-xl px-8 text-[10px] font-black uppercase tracking-widest"
          >
            {tripTableText.clearFilters}
          </Button>
        )}
      </motion.div>
    );
  }

  return (
    <div
      ref={parentRef}
      className="custom-scrollbar mt-8 overflow-y-auto pr-2"
      style={{ maxHeight: "calc(100vh - 420px)" }}
    >
      <div
        style={{
          height: `${rowVirtualizer.getTotalSize()}px`,
          width: "100%",
          position: "relative",
        }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const trip = trips[virtualRow.index];
          const isSelected = selectedIds.includes(trip.id!);
          const statusConfig = getStatusConfig(trip.durum);
          const statusStyles = getStatusStyles(trip.durum);

          return (
            <div
              key={virtualRow.key}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: `${virtualRow.size}px`,
                transform: `translateY(${virtualRow.start}px)`,
                paddingBottom: "16px",
              }}
            >
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                onClick={() => onViewDetails?.(trip)}
                className={cn(
                  "group relative flex h-full cursor-pointer overflow-hidden rounded-modal border border-border/40 transition-all duration-300",
                  "glass",
                  isSelected
                    ? "border-accent/20 bg-accent/[0.03] ring-2 ring-accent/40 shadow-lg shadow-accent/5"
                    : "hover:border-accent/30 hover:bg-elevated",
                )}
              >
                <div
                  className={cn(
                    "h-full w-1.5 shrink-0 transition-all duration-500",
                    isSelected ? "bg-accent" : statusStyles.bar,
                  )}
                />

                <div className="grid flex-1 grid-cols-12 items-center gap-6 p-6">
                  <div className="col-span-12 flex flex-col items-center gap-3 lg:col-span-1">
                    <button
                      onClick={(event) => {
                        event.stopPropagation();
                        onToggleSelection?.(trip.id!);
                      }}
                      className={cn(
                        "flex h-6 w-6 items-center justify-center rounded-lg border-2 transition-all",
                        isSelected
                          ? "border-accent bg-accent text-white shadow-md shadow-accent/20"
                          : "border-border/60 bg-transparent hover:border-accent/40",
                      )}
                    >
                      {isSelected && <Check size={14} strokeWidth={3} />}
                    </button>
                    <span className="text-[9px] font-black tracking-tighter text-tertiary tabular-nums">
                      #{trip.id}
                    </span>
                  </div>

                  <div className="col-span-12 lg:col-span-3">
                    <div className="flex flex-col gap-1.5">
                      <div className="flex items-center gap-2">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-border/40 bg-elevated transition-colors group-hover:border-accent/20 group-hover:bg-accent/5 group-hover:text-accent">
                          <Route size={16} />
                        </div>
                        <h4 className="truncate text-[15px] font-black tracking-tight text-primary transition-colors group-hover:text-accent">
                          {trip.cikis_yeri}{" "}
                          <span className="mx-1 text-tertiary opacity-40">
                            →
                          </span>{" "}
                          {trip.varis_yeri}
                        </h4>
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5 pl-10">
                        <span className="inline-flex items-center rounded-full border border-border/40 bg-elevated px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-secondary">
                          {trip.sefer_no ||
                            tripTableText.fallbackTripNumber(trip.id)}
                        </span>
                        {trip.bos_sefer && (
                          <span className="inline-flex items-center gap-1 rounded-full border border-info/30 bg-info/10 px-2 py-1 text-[9px] font-black uppercase tracking-widest text-info">
                            {tripTableText.bosSefer}
                          </span>
                        )}
                        {trip.is_round_trip && (
                          <span className="inline-flex items-center gap-1 rounded-full border border-accent/30 bg-accent/10 px-2 py-1 text-[9px] font-black uppercase tracking-widest text-accent">
                            <ArrowLeftRight size={9} />
                            {tripTableText.roundTrip}
                          </span>
                        )}
                        {trip.version != null && trip.version > 1 && (
                          <span className="inline-flex items-center gap-1 rounded-full border border-border/40 bg-elevated px-2 py-1 text-[9px] font-black tracking-widest text-tertiary">
                            <Layers size={9} />
                            {tripTableText.versionLabel(trip.version)}
                          </span>
                        )}
                      </div>
                      <div className="mt-1 flex items-center gap-3 pl-10">
                        <div className="flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest text-secondary">
                          <Calendar size={12} className="opacity-40" />
                          {trip.tarih}
                        </div>
                        <div className="ml-auto flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest text-tertiary">
                          <Clock size={12} className="opacity-40" />
                          {trip.saat}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="col-span-12 grid grid-cols-2 gap-6 border-x border-border/20 px-6 md:col-span-6 lg:col-span-4">
                    <div className="space-y-2">
                      <label className="text-[9px] font-black uppercase tracking-[0.2em] text-tertiary">
                        {tripTableText.vehicleLabel}
                      </label>
                      <div className="flex flex-col">
                        <Link
                          to={`/fleet?search=${encodeURIComponent(
                            trip.arac?.plaka ||
                              trip.arac_plaka ||
                              trip.plaka ||
                              "",
                          )}`}
                          onClick={(e) => e.stopPropagation()}
                          className="text-sm font-black tracking-tight text-primary tabular-nums transition-colors hover:text-accent"
                        >
                          {trip.arac?.plaka ||
                            trip.arac_plaka ||
                            trip.plaka ||
                            tripTableText.unknownValue}
                        </Link>
                        <span className="mt-0.5 text-[10px] font-bold uppercase tracking-tight text-secondary opacity-60">
                          {trip.dorse?.plaka ||
                            (trip.dorse_id
                              ? tripTableText.trailerFallback(trip.dorse_id)
                              : tripTableText.noTrailer)}
                        </span>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <label className="text-[9px] font-black uppercase tracking-[0.2em] text-tertiary">
                        {tripTableText.driverLabel}
                      </label>
                      <Link
                        to={`/drivers?search=${encodeURIComponent(
                          trip.sofor?.ad_soyad ||
                            trip.sofor_ad_soyad ||
                            trip.sofor_adi ||
                            "",
                        )}`}
                        onClick={(e) => e.stopPropagation()}
                        className="truncate text-sm font-black uppercase tracking-tight text-primary transition-colors hover:text-accent"
                      >
                        {trip.sofor?.ad_soyad ||
                          trip.sofor_ad_soyad ||
                          trip.sofor_adi ||
                          tripTableText.unknownValue}
                      </Link>
                    </div>
                  </div>

                  <div className="col-span-12 pr-2 md:col-span-6 lg:col-span-3">
                    <div className="mb-3 flex items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span
                          className={cn(
                            "flex items-center rounded-xl border px-3 py-1.5 text-[10px] font-black uppercase tracking-widest",
                            statusStyles.bg,
                            statusStyles.text,
                            statusStyles.border,
                          )}
                        >
                          {statusStyles.icon}
                          {statusConfig.text}
                        </span>
                        {trip.onay_durumu === "beklemede" && (
                          <span className="flex items-center rounded-xl border border-warning/30 bg-warning/10 px-2 py-1.5 text-[10px] font-black uppercase tracking-widest text-warning">
                            Onay Bekliyor
                          </span>
                        )}
                        {(() => {
                          if (
                            trip.duration_min &&
                            trip.predicted_duration_min
                          ) {
                            const diff =
                              trip.duration_min - trip.predicted_duration_min;
                            if (Math.abs(diff) >= 15) {
                              return diff > 0 ? (
                                <span className="flex items-center gap-1 rounded-xl border border-warning/30 bg-warning/10 px-2 py-1.5 text-[9px] font-black uppercase tracking-widest text-warning">
                                  <Clock size={9} />
                                  {tripTableText.delayed(diff)}
                                </span>
                              ) : (
                                <span className="flex items-center gap-1 rounded-xl border border-success/30 bg-success/10 px-2 py-1.5 text-[9px] font-black uppercase tracking-widest text-success">
                                  <Clock size={9} />
                                  {tripTableText.early(Math.abs(diff))}
                                </span>
                              );
                            }
                          }
                          return null;
                        })()}
                      </div>
                      <span className="text-xs font-black tracking-tighter text-primary tabular-nums">
                        %{statusConfig.progress}
                      </span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full border border-border/20 bg-black/10 p-[1px]">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${statusConfig.progress}%` }}
                        className={cn(
                          "h-full rounded-full shadow-[0_0_8px]",
                          statusStyles.glow.replace("shadow-", "shadow-"),
                          statusStyles.bar.replace("bg-", "bg-"),
                        )}
                        transition={{ duration: 1, ease: "circOut" }}
                      />
                    </div>
                    {normalizeTripStatus(trip.durum) ===
                      TRIP_STATUS_TAMAMLANDI &&
                      trip.gercek_tuketim != null && (
                        <div className="mt-2 flex items-center gap-1.5 text-[10px] font-black text-secondary">
                          <Droplet size={10} className="text-info opacity-60" />
                          <span className="text-tertiary">
                            {tripTableText.actualConsumption}:
                          </span>
                          <span className="tabular-nums text-primary">
                            {trip.gercek_tuketim.toFixed(1)} L/100km
                          </span>
                        </div>
                      )}
                    {(() => {
                      if (trip.km_baslangic != null && trip.km_bitis != null) {
                        const odomDist = trip.km_bitis - trip.km_baslangic;
                        const diff = Math.round(odomDist - trip.mesafe_km);
                        if (Math.abs(diff) > 20) {
                          return (
                            <div className="mt-1 flex items-center gap-1 text-[9px] font-black text-warning">
                              <AlertTriangle size={9} />
                              {tripTableText.odometerWarning(diff)}
                            </div>
                          );
                        }
                      }
                      return null;
                    })()}
                    {trip.onay_durumu === "reddedildi" && trip.onay_notu && (
                      <div className="mt-2 rounded-card border border-danger/20 bg-danger/5 px-2.5 py-1.5">
                        <p className="text-[9px] font-black uppercase tracking-widest text-danger/60">
                          {tripTableText.rejectionReason}
                        </p>
                        <p className="mt-0.5 text-[10px] font-medium text-danger leading-snug">
                          {trip.onay_notu}
                        </p>
                      </div>
                    )}
                  </div>

                  <div className="col-span-12 flex items-center justify-end gap-1.5 lg:col-span-1">
                    {canWrite && (
                      <button
                        onClick={(event) => {
                          event.stopPropagation();
                          onEdit(trip);
                        }}
                        className="flex h-10 w-10 items-center justify-center rounded-xl border border-border/40 bg-elevated text-tertiary transition-all hover:border-accent/30 hover:bg-accent/10 hover:text-accent"
                      >
                        <Edit2 size={16} />
                      </button>
                    )}

                    <div
                      className="group/menu relative"
                      ref={openMenuTripId === trip.id ? menuWrapRef : undefined}
                    >
                      <button
                        type="button"
                        aria-label={tripTableText.openMenu}
                        aria-expanded={openMenuTripId === trip.id}
                        onClick={(event) => {
                          event.stopPropagation();
                          setOpenMenuTripId(
                            openMenuTripId === trip.id ? null : trip.id ?? null,
                          );
                        }}
                        className="flex h-10 w-10 items-center justify-center rounded-xl border border-border/40 bg-elevated text-tertiary transition-all hover:bg-elevated hover:text-primary"
                      >
                        <MoreVertical size={18} />
                      </button>
                      <div
                        className={cn(
                          "absolute bottom-full right-0 z-[100] mb-3 w-56 origin-bottom-right rounded-modal border border-border/60 bg-surface/90 p-2 shadow-2xl backdrop-blur-xl transition-all duration-300",
                          // Hover state korunur (UX),
                          // JS state'i ile de açılır
                          // (Playwright + click)
                          openMenuTripId === trip.id
                            ? "pointer-events-auto scale-100 opacity-100"
                            : "pointer-events-none scale-95 opacity-0 group-hover/menu:pointer-events-auto group-hover/menu:scale-100 group-hover/menu:opacity-100",
                        )}
                      >
                        {canApprove && trip.onay_durumu === "beklemede" && (
                          <>
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                onOnayla?.(trip);
                              }}
                              className="flex w-full items-center gap-3 rounded-card px-4 py-3 text-xs font-black uppercase tracking-widest text-success transition-all hover:bg-success/10 hover:text-success"
                            >
                              <CheckCircle size={14} />
                              Onayla
                            </button>
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                onReddet?.(trip);
                              }}
                              className="flex w-full items-center gap-3 rounded-card px-4 py-3 text-xs font-black uppercase tracking-widest text-danger transition-all hover:bg-danger/10"
                            >
                              <XCircle size={14} />
                              Reddet
                            </button>
                            <div className="mx-3 my-2 h-px bg-border/40" />
                          </>
                        )}
                        <button
                          onClick={(event) => {
                            event.stopPropagation();
                            onCreateReturn?.(trip);
                          }}
                          className="flex w-full items-center gap-3 rounded-card px-4 py-3 text-xs font-black uppercase tracking-widest text-secondary transition-all hover:bg-accent/10 hover:text-accent"
                        >
                          <RefreshCw size={14} />
                          {tripTableText.createReturn}
                        </button>
                        <button
                          onClick={(event) => {
                            event.stopPropagation();
                            onStatusChange?.(trip);
                          }}
                          className="flex w-full items-center gap-3 rounded-card px-4 py-3 text-xs font-black uppercase tracking-widest text-secondary transition-all hover:bg-elevated hover:text-primary"
                        >
                          <Settings size={14} />
                          {tripTableText.updateStatus}
                        </button>
                        {onCostAnalysis && (
                          <button
                            onClick={(event) => {
                              event.stopPropagation();
                              onCostAnalysis(trip);
                            }}
                            className="flex w-full items-center gap-3 rounded-card px-4 py-3 text-xs font-black uppercase tracking-widest text-secondary transition-all hover:bg-accent/10 hover:text-accent"
                          >
                            <Calculator size={14} />
                            {tripTableText.costAnalysis}
                          </button>
                        )}
                        {canWrite && (
                          <>
                            <div className="mx-3 my-2 h-px bg-border/40" />
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                onDelete(trip);
                              }}
                              className="flex w-full items-center gap-3 rounded-card px-4 py-3 text-xs font-black uppercase tracking-widest text-danger transition-all hover:bg-danger/10"
                            >
                              <Trash2 size={14} />
                              {tripTableText.deleteTrip}
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="absolute right-0 top-0 flex h-full w-12 translate-x-4 items-center justify-center bg-gradient-to-l from-accent/5 to-transparent opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100">
                  <ChevronRight className="text-accent/40" size={24} />
                </div>
              </motion.div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
