import { FuelStats as FuelStatsModel } from "../../types";
import {
  Droplets,
  TrendingUp,
  Wallet,
  Activity,
  MapPin,
  AlertTriangle,
} from "lucide-react";
import { motion } from "framer-motion";
import { fuelStatsText } from "../../resources/tr/fuel";
import { useAnomalyCount } from "../../hooks/useAnomalyCount";

interface FuelStatsProps {
  stats: FuelStatsModel | null;
  loading: boolean;
}

export function FuelStats({ stats, loading }: FuelStatsProps) {
  const formatCurrency = (value: number) =>
    new Intl.NumberFormat("tr-TR", {
      style: "currency",
      currency: "TRY",
      maximumFractionDigits: 0,
    }).format(value);

  // Aynı queryKey'i FuelAnomalyWidget ile paylaşan ortak hook —
  // TanStack Query cache üzerinden tek HTTP isteğine indirgenir.
  const { count: anomalyCount, isLoaded: anomalyLoaded } = useAnomalyCount(
    "tuketim",
    30,
  );

  if (!loading && !stats) {
    return (
      <div className="rounded-2xl border border-border bg-surface px-6 py-5 text-sm text-secondary shadow-sm">
        {fuelStatsText.unavailable}
      </div>
    );
  }

  const hasData = (stats?.total_consumption ?? 0) > 0;
  const totalDistance = stats?.total_distance ?? 0;

  const items = [
    {
      label: fuelStatsText.totalConsumption,
      value: hasData
        ? `${(stats?.total_consumption ?? 0).toLocaleString("tr-TR", {
            maximumFractionDigits: 0,
          })} L`
        : "—",
      icon: Droplets,
      color: "text-info",
      bg: "bg-info/10",
    },
    {
      label: fuelStatsText.totalCost,
      value: hasData ? formatCurrency(stats?.total_cost ?? 0) : "—",
      icon: Wallet,
      color: "text-warning",
      bg: "bg-warning/10",
    },
    {
      label: fuelStatsText.averageConsumption,
      value: hasData
        ? `${(stats?.avg_consumption ?? 0).toFixed(1)} L/100km`
        : "—",
      icon: Activity,
      color: "text-accent",
      bg: "bg-accent/10",
    },
    {
      label: fuelStatsText.averagePrice,
      value: hasData ? `${(stats?.avg_price ?? 0).toFixed(2)} TL/L` : "—",
      icon: TrendingUp,
      color: "text-success",
      bg: "bg-success/10",
    },
    {
      label: fuelStatsText.totalDistance,
      value:
        totalDistance > 0
          ? `${totalDistance.toLocaleString("tr-TR", {
              maximumFractionDigits: 0,
            })} km`
          : "—",
      icon: MapPin,
      color: "text-info",
      bg: "bg-info/10",
    },
    {
      label: fuelStatsText.fuelAnomalies,
      value: anomalyLoaded ? anomalyCount.toString() : "—",
      icon: AlertTriangle,
      color: anomalyCount > 0 ? "text-danger" : "text-success",
      bg: anomalyCount > 0 ? "bg-danger/10" : "bg-success/10",
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-6 mb-8">
      {items.map((item, index) => (
        <motion.div
          key={item.label}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.08 }}
          className="bg-surface p-6 flex flex-col justify-between flex-1 relative overflow-hidden group border border-border rounded-2xl shadow-sm"
        >
          <div
            className={`absolute -right-6 -top-6 opacity-[0.08] transform rotate-12 transition-transform group-hover:scale-110 ${item.color}`}
          >
            <item.icon className="w-32 h-32" />
          </div>

          <div className="relative z-10">
            <div
              className={`inline-flex items-center justify-center w-9 h-9 rounded-xl mb-3 ${item.bg}`}
            >
              <item.icon className={`w-4 h-4 ${item.color}`} />
            </div>
            <p className="text-secondary text-[10px] font-bold uppercase tracking-widest mb-1">
              {item.label}
            </p>
            {loading ? (
              <div className="h-8 w-24 bg-elevated animate-pulse rounded-lg mt-1" />
            ) : (
              <h4 className="text-3xl font-black text-primary tracking-tighter">
                {item.value}
              </h4>
            )}
          </div>

          <div className="flex items-center gap-2 mt-4 relative z-10">
            <span className="text-secondary text-[10px] font-bold uppercase">
              {fuelStatsText.verifiedDataHint}
            </span>
          </div>
        </motion.div>
      ))}
    </div>
  );
}
