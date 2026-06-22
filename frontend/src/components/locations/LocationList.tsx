import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Clock,
  Database,
  Droplets,
  Edit2,
  Info,
  MapPin,
  Mountain,
  Trash2,
  TrendingUp,
  Wind,
  Zap,
} from "lucide-react";

import { Location } from "../../types/location";
import { cn } from "../../lib/utils";
import { Button } from "../ui/Button";
import { useLocationsResources } from "../../resources/useResources";

interface LocationListProps {
  locations: Location[];
  loading: boolean;
  onEdit: (location: Location) => void;
  onDelete: (location: Location) => void;
  onAnalyze: (location: Location) => void;
  onAdd: () => void;
  viewMode: "table" | "grid";
}

const SkeletonRow = () => (
  <tr className="animate-pulse border-b border-border/20">
    <td className="px-8 py-6">
      <div className="h-4 w-32 rounded bg-elevated" />
    </td>
    <td className="px-8 py-6">
      <div className="h-4 w-32 rounded bg-elevated" />
    </td>
    <td className="px-8 py-6">
      <div className="h-4 w-20 rounded bg-elevated" />
    </td>
    <td className="px-8 py-6">
      <div className="h-4 w-16 rounded bg-elevated" />
    </td>
    <td className="px-8 py-6">
      <div className="h-4 w-24 rounded bg-elevated" />
    </td>
    <td className="px-8 py-6">
      <div className="h-4 w-28 rounded bg-elevated" />
    </td>
    <td className="px-8 py-6 text-right">
      <div className="ml-auto h-10 w-32 rounded-xl bg-elevated" />
    </td>
  </tr>
);

export function LocationList({
  locations,
  loading,
  onEdit,
  onDelete,
  onAnalyze,
  onAdd,
}: LocationListProps) {
  const { locationListText } = useLocationsResources();
  const getDifficultyConfig = (difficulty: string) => {
    switch (difficulty) {
      case "Zor":
        return {
          label: locationListText.difficulty.hard,
          icon: <Mountain size={12} strokeWidth={3} />,
          bg: "bg-danger/5 text-danger border-danger/30 shadow-danger/5",
        };
      case "Orta":
        return {
          label: locationListText.difficulty.medium,
          icon: <TrendingUp size={12} strokeWidth={3} />,
          bg: "bg-warning/5 text-warning border-warning/30 shadow-warning/5",
        };
      default:
        return {
          label: locationListText.difficulty.easy,
          icon: <Wind size={12} strokeWidth={3} />,
          bg: "bg-success/5 text-success border-success/30 shadow-success/5",
        };
    }
  };
  const getSourceConfig = (
    source: string | undefined,
    isCorrected: boolean | null | undefined,
  ) => {
    if (isCorrected) {
      return {
        label: locationListText.source.corrected,
        bg: "bg-warning/5 text-warning border-warning/30",
        icon: <AlertTriangle size={10} strokeWidth={3} />,
      };
    }
    switch (source?.toLowerCase()) {
      case "mapbox_hybrid":
      case "mapbox":
        return {
          label: locationListText.source.verified,
          bg: "bg-info/5 text-info border-info/30 shadow-info/5",
          icon: <Zap size={10} strokeWidth={3} />,
        };
      default:
        return {
          label: locationListText.source.standard,
          bg: "bg-elevated text-tertiary border-border/40",
          icon: <Database size={10} strokeWidth={3} />,
        };
    }
  };
  function getAnalysisFreshness(lastApiCall: string | null | undefined): {
    label: string;
    isStale: boolean;
  } {
    if (!lastApiCall)
      return { label: locationListText.freshness.never, isStale: true };
    const days = Math.floor(
      (Date.now() - new Date(lastApiCall).getTime()) / 86_400_000,
    );
    if (days > 90)
      return { label: locationListText.freshness.stale(days), isStale: true };
    if (days > 30)
      return { label: locationListText.freshness.old(days), isStale: false };
    return { label: locationListText.freshness.fresh(days), isStale: false };
  }
  if (loading) {
    return (
      <div className="overflow-hidden rounded-[32px] border border-border/40 shadow-2xl glass">
        <table className="w-full border-collapse text-left">
          <thead className="border-b border-border/20 bg-elevated text-[10px] font-black uppercase tracking-[0.2em] text-tertiary">
            <tr>
              <th className="px-8 py-5">
                {locationListText.headers.routeInfo}
              </th>
              <th className="px-8 py-5">
                {locationListText.headers.destination}
              </th>
              <th className="px-8 py-5">{locationListText.headers.distance}</th>
              <th className="px-8 py-5">
                {locationListText.headers.fuelEstimate}
              </th>
              <th className="px-8 py-5">
                {locationListText.headers.difficulty}
              </th>
              <th className="px-8 py-5">{locationListText.headers.analysis}</th>
              <th className="px-8 py-5 text-right">
                {locationListText.headers.actions}
              </th>
            </tr>
          </thead>
          <tbody>
            {[1, 2, 3, 4, 5].map((index) => (
              <SkeletonRow key={index} />
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (locations.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="group flex flex-col items-center justify-center rounded-[40px] border-2 border-dashed border-border/40 px-10 py-32 text-center transition-all hover:bg-elevated glass"
      >
        <div className="mb-8 flex h-24 w-24 items-center justify-center rounded-full border border-accent/10 bg-accent/5 transition-transform duration-500 group-hover:scale-110">
          <MapPin size={48} strokeWidth={1.5} className="text-accent/40" />
        </div>
        <h3 className="mb-3 text-2xl font-black uppercase tracking-tight text-primary">
          {locationListText.emptyTitle}
        </h3>
        <p className="mb-10 max-w-sm text-sm font-medium leading-relaxed text-secondary">
          {locationListText.emptyDescription}
        </p>
        <button
          onClick={onAdd}
          className="flex items-center gap-3 rounded-2xl bg-accent px-10 py-4 text-xs font-black uppercase tracking-widest text-white shadow-xl shadow-accent/20 transition-all active:scale-95 hover:bg-accent/80"
        >
          <Zap size={18} strokeWidth={3} />
          {locationListText.addRoute}
        </button>
      </motion.div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[32px] border border-border/40 shadow-2xl glass">
      <div className="flex items-center justify-between border-b border-border/20 bg-elevated px-8 py-6">
        <div className="flex items-center gap-3">
          <div className="h-6 w-1.5 rounded-full bg-accent" />
          <h3 className="text-sm font-black uppercase tracking-[0.15em] text-primary">
            {locationListText.listTitle}
          </h3>
        </div>
      </div>
      <div className="custom-scrollbar overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead className="border-b border-border/20 bg-elevated text-[10px] font-black uppercase tracking-[0.2em] text-tertiary">
            <tr>
              <th className="px-8 py-5">
                {locationListText.headers.routeInfo}
              </th>
              <th className="px-8 py-5">
                {locationListText.headers.destination}
              </th>
              <th className="px-8 py-5">{locationListText.headers.distance}</th>
              <th className="px-8 py-5">
                {locationListText.headers.fuelEstimate}
              </th>
              <th className="px-8 py-5">
                {locationListText.headers.difficulty}
              </th>
              <th className="px-8 py-5">{locationListText.headers.analysis}</th>
              <th className="px-8 py-5 text-right">
                {locationListText.headers.actions}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/20 text-sm text-primary">
            {locations.map((location, index) => {
              const difficulty = getDifficultyConfig(location.zorluk);
              const freshness = getAnalysisFreshness(location.last_api_call);
              const source = getSourceConfig(
                location.source || undefined,
                location.is_corrected,
              );

              return (
                <motion.tr
                  key={location.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className="group transition-colors hover:bg-accent/[0.02]"
                >
                  <td className="px-8 py-6">
                    <div className="flex items-center gap-4">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-accent/20 bg-accent/5 text-accent shadow-lg shadow-accent/5 transition-all duration-500 group-hover:rotate-3 group-hover:scale-110">
                        <MapPin size={16} strokeWidth={2.5} />
                      </div>
                      <span className="text-[15px] font-black uppercase tracking-tight text-primary">
                        {location.cikis_yeri}
                      </span>
                    </div>
                  </td>
                  <td className="px-8 py-6">
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-border/40 bg-elevated text-accent/40 transition-colors group-hover:text-accent">
                        <ArrowRight size={14} strokeWidth={3} />
                      </div>
                      <span className="text-[14px] font-black uppercase tracking-tight text-secondary">
                        {location.varis_yeri}
                      </span>
                    </div>
                  </td>
                  <td className="px-8 py-6">
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-lg font-black tracking-tighter text-primary tabular-nums">
                        {location.mesafe_km}
                      </span>
                      <span className="text-[9px] font-black uppercase tracking-widest text-tertiary opacity-60">
                        KM
                      </span>
                    </div>
                  </td>
                  <td className="px-8 py-6">
                    {location.tahmini_yakit_lt ? (
                      <div className="flex items-center gap-1.5">
                        <Droplets
                          size={13}
                          className="text-info/60"
                          strokeWidth={2.5}
                        />
                        <span className="text-sm font-black tabular-nums text-primary">
                          {Math.round(location.tahmini_yakit_lt)}
                        </span>
                        <span className="text-[9px] font-black uppercase tracking-widest text-tertiary opacity-60">
                          L
                        </span>
                        <span
                          className="ml-0.5 inline-flex h-4 w-4 cursor-help items-center justify-center text-tertiary"
                          title={locationListText.fuelEstimateTooltip}
                          aria-label={locationListText.fuelEstimateTooltip}
                        >
                          <Info size={11} />
                        </span>
                      </div>
                    ) : (
                      <span className="text-[10px] text-tertiary">—</span>
                    )}
                  </td>
                  <td className="px-8 py-6">
                    <div
                      className={cn(
                        "inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-[9px] font-black uppercase tracking-widest shadow-lg",
                        difficulty.bg,
                      )}
                    >
                      {difficulty.icon}
                      {difficulty.label}
                    </div>
                  </td>
                  <td className="px-8 py-6">
                    <div className="flex flex-col gap-2.5">
                      <div className="flex gap-3 text-[10px] font-black uppercase tracking-widest tabular-nums">
                        <span className="flex items-center gap-1.5 text-success">
                          <TrendingUp size={12} className="rotate-0" />
                          {locationListText.analysisMetrics.ascent}:{" "}
                          {location.ascent_m || 0}M
                        </span>
                        <span className="flex items-center gap-1.5 text-danger">
                          <TrendingUp size={12} className="rotate-180" />
                          {locationListText.analysisMetrics.descent}:{" "}
                          {location.descent_m || 0}M
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div
                          className={cn(
                            "flex items-center gap-2 rounded-lg border px-2.5 py-1 text-[9px] font-black uppercase tracking-widest",
                            source.bg,
                          )}
                          title={location.correction_reason || undefined}
                        >
                          {source.icon}
                          {source.label}
                        </div>
                        <div
                          className={cn(
                            "flex items-center gap-1 rounded-lg border px-2 py-1 text-[9px] font-black uppercase tracking-widest",
                            freshness.isStale
                              ? "border-warning/30 bg-warning/5 text-warning"
                              : "border-border/30 bg-elevated text-tertiary",
                          )}
                        >
                          <Clock size={9} strokeWidth={3} />
                          {freshness.label}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-8 py-6 text-right">
                    <div className="flex translate-x-4 items-center justify-end gap-2 opacity-0 transition-all duration-300 group-hover:translate-x-0 group-hover:opacity-100">
                      <Button
                        variant="secondary"
                        onClick={() => onAnalyze(location)}
                        className="flex h-10 items-center gap-2.5 rounded-xl border-accent/20 bg-accent/5 px-4 text-[10px] font-black uppercase tracking-widest text-accent shadow-lg shadow-accent/5 hover:bg-accent hover:text-white"
                      >
                        <Activity size={14} strokeWidth={3} />
                        {locationListText.actions.analyze}
                      </Button>
                      <button
                        onClick={() => onEdit(location)}
                        aria-label={locationListText.actions.edit}
                        className="flex h-10 w-10 items-center justify-center rounded-xl border border-border/40 bg-elevated text-tertiary transition-all active:scale-90 hover:border-warning/30 hover:bg-warning/10 hover:text-warning"
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        onClick={() => onDelete(location)}
                        aria-label={locationListText.actions.delete}
                        className="flex h-10 w-10 items-center justify-center rounded-xl border border-border/40 bg-elevated text-tertiary transition-all active:scale-90 hover:border-danger/30 hover:bg-danger/10 hover:text-danger"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
