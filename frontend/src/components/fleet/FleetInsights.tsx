import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { driverService } from "../../api/drivers";
import { reportService } from "../../api/reports";
import { vehicleService } from "../../api/vehicles";
import { dorseService } from "../../services/dorseService";
import { cn } from "../../lib/utils";
import { useFleetResources } from "../../resources/useResources";
import { InspectionAlertModal } from "../vehicles/InspectionAlertModal";

interface StatProps {
  title: string;
  value: string;
  unit?: string;
  className?: string;
  hint?: string;
  onClick?: () => void;
}

function StatCard({
  title,
  value,
  unit,
  className = "",
  hint,
  onClick,
}: StatProps) {
  const interactive = !!onClick;
  const Component = interactive ? "button" : "div";
  return (
    <Component
      type={interactive ? "button" : undefined}
      onClick={onClick}
      className={cn(
        "rounded-card border border-border bg-surface p-5 shadow-sm transition-all hover:shadow-md text-left w-full",
        interactive &&
          "cursor-pointer hover:border-accent/30 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40",
        className,
      )}
    >
      <p className="mb-1 text-[11px] font-bold uppercase tracking-widest text-secondary">
        {title}
      </p>
      <div className="flex items-baseline gap-2">
        <span className="text-3xl font-bold tracking-tight text-primary">
          {value}
        </span>
        {unit && (
          <span className="text-sm font-medium text-secondary">{unit}</span>
        )}
      </div>
      {hint && (
        <p className="mt-1 text-[10px] font-medium text-secondary truncate">
          {hint}
        </p>
      )}
    </Component>
  );
}

interface FleetInsightsTextShape {
  labels: { trailers: string; drivers: string; fallback: string };
  cards: {
    inspectionHint: (expiring: number, overdue: number) => string;
    vehicleUnit: string;
    inspectionOk: string;
  };
}

async function getNonVehicleSummary(
  activeTab: string,
  t: FleetInsightsTextShape,
) {
  if (activeTab === "trailers") {
    const stats = await dorseService.getFleetStats();
    return {
      label: t.labels.trailers,
      total: stats.total,
      active: stats.active,
      inspection_expiring: stats.inspection_expiring,
      inspection_overdue: stats.inspection_overdue,
    };
  }

  const stats = await driverService.getFleetStats();
  return {
    label: t.labels.drivers,
    total: stats.total,
    active: stats.active,
    inspection_expiring: 0,
    inspection_overdue: 0,
  };
}

export function FleetInsights({
  activeTab = "vehicles",
}: {
  activeTab?: string;
}) {
  const { fleetInsightsText } = useFleetResources();
  const isVehiclesTab = activeTab === "vehicles";
  const [isInspectionModalOpen, setIsInspectionModalOpen] = useState(false);

  const { data: fleetStats, isLoading: isFleetStatsLoading } = useQuery({
    queryKey: ["vehicle-fleet-stats"],
    queryFn: () => vehicleService.getFleetStats(),
    enabled: isVehiclesTab,
    staleTime: 5 * 60 * 1000,
  });

  const { data: nonVehicleSummary, isLoading: isNonVehicleLoading } = useQuery({
    queryKey: ["fleet-non-vehicle-summary", activeTab],
    queryFn: () => getNonVehicleSummary(activeTab, fleetInsightsText),
    enabled: !isVehiclesTab,
  });

  const { data: dashboard } = useQuery({
    queryKey: ["fleet-dashboard-summary"],
    queryFn: () => reportService.getDashboardStats(),
    staleTime: 5 * 60 * 1000,
  });

  const isLoading = isVehiclesTab ? isFleetStatsLoading : isNonVehicleLoading;

  if (isLoading) {
    return (
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-4">
        {[1, 2, 3, 4].map((index) => (
          <div
            key={index}
            className="h-28 animate-pulse rounded-card border border-border bg-elevated/50"
          />
        ))}
      </div>
    );
  }

  if (isVehiclesTab && fleetStats) {
    const hasInspectionIssue =
      fleetStats.inspection_overdue > 0 || fleetStats.inspection_expiring > 0;
    const inspectionCount =
      fleetStats.inspection_overdue + fleetStats.inspection_expiring;

    return (
      <div className="mb-2 grid grid-cols-1 gap-4 sm:grid-cols-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <StatCard
            title={fleetInsightsText.cards.total(
              fleetInsightsText.labels.vehicles,
            )}
            value={String(fleetStats.total)}
            className="border-l-[3px] border-l-accent/60"
          />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <StatCard
            title={fleetInsightsText.cards.active(
              fleetInsightsText.labels.vehicles,
            )}
            value={String(fleetStats.active)}
          />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <StatCard
            title={fleetInsightsText.cards.trips}
            value={String(dashboard?.toplam_sefer ?? 0)}
            unit={fleetInsightsText.cards.recordsUnit}
          />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <StatCard
            title={fleetInsightsText.cards.inspectionWarning}
            value={String(inspectionCount)}
            unit={fleetInsightsText.cards.vehicleUnit}
            hint={
              hasInspectionIssue
                ? fleetInsightsText.cards.inspectionHint(
                    fleetStats.inspection_expiring,
                    fleetStats.inspection_overdue,
                  )
                : fleetInsightsText.cards.inspectionOk
            }
            className={cn(
              hasInspectionIssue && inspectionCount > 0
                ? "border-l-[3px] border-l-warning/60"
                : "border-l-[3px] border-l-success/60",
            )}
            onClick={
              inspectionCount > 0
                ? () => setIsInspectionModalOpen(true)
                : undefined
            }
          />
        </motion.div>

        <InspectionAlertModal
          isOpen={isInspectionModalOpen}
          onClose={() => setIsInspectionModalOpen(false)}
        />
      </div>
    );
  }

  const label = nonVehicleSummary?.label || fleetInsightsText.labels.fallback;

  return (
    <div className="mb-2 grid grid-cols-1 gap-4 sm:grid-cols-3">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <StatCard
          title={fleetInsightsText.cards.total(label)}
          value={String(nonVehicleSummary?.total ?? 0)}
          className="border-l-[3px] border-l-accent/60"
        />
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <StatCard
          title={fleetInsightsText.cards.active(label)}
          value={String(nonVehicleSummary?.active ?? 0)}
        />
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <StatCard
          title={fleetInsightsText.cards.trips}
          value={String(dashboard?.toplam_sefer ?? 0)}
          unit={fleetInsightsText.cards.recordsUnit}
        />
      </motion.div>
    </div>
  );
}
