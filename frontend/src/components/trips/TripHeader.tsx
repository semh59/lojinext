import { motion } from "framer-motion";
import { Plus, TrendingUp, Truck } from "lucide-react";

import { cn } from "../../lib/utils";
import { Button } from "../ui/Button";
import { useTripsResources } from "../../resources/useResources";

interface TripHeaderProps {
  onAdd: () => void;
  showCharts: boolean;
  onToggleCharts: () => void;
}

export function TripHeader({
  onAdd,
  showCharts,
  onToggleCharts,
}: TripHeaderProps) {
  const { tripHeaderText } = useTripsResources();
  return (
    <div className="relative z-40 mb-10 flex flex-col items-start justify-between gap-6 md:flex-row md:items-center">
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        className="flex items-center gap-5"
      >
        <div className="flex h-14 w-14 items-center justify-center rounded-[20px] border border-accent/10 bg-accent/5 text-accent shadow-inner">
          <Truck size={32} strokeWidth={2.5} />
        </div>
        <div>
          <h1 className="text-2xl font-black leading-tight tracking-tight text-primary">
            {tripHeaderText.title}
          </h1>
          <div className="mt-1 flex items-center gap-2">
            <span className="text-[10px] font-black uppercase tracking-[0.2em] text-accent">
              {tripHeaderText.subtitlePrimary}
            </span>
            <div className="h-1 w-1 rounded-full bg-border" />
            <span className="text-[10px] font-black uppercase tracking-[0.2em] text-tertiary opacity-60">
              {tripHeaderText.subtitleSecondary}
            </span>
          </div>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        className="flex w-full items-center gap-3 md:w-auto"
      >
        <Button
          onClick={onToggleCharts}
          variant="secondary"
          aria-label={
            showCharts
              ? tripHeaderText.hideAnalytics
              : tripHeaderText.showAnalytics
          }
          className={cn(
            "flex-1 gap-3 rounded-2xl border px-6 text-xs font-black uppercase tracking-widest transition-all md:flex-none",
            "h-12",
            showCharts
              ? "border-accent/30 bg-accent/10 text-accent shadow-lg shadow-accent/5 ring-1 ring-accent/20"
              : "border-border bg-surface text-secondary hover:text-primary",
          )}
        >
          <TrendingUp
            size={18}
            className={cn(
              "transition-transform duration-500",
              showCharts && "rotate-12",
            )}
          />
          {showCharts
            ? tripHeaderText.hideAnalytics
            : tripHeaderText.showAnalytics}
        </Button>

        <Button
          onClick={onAdd}
          variant="primary"
          aria-label={tripHeaderText.createTripAria}
          className="flex h-12 flex-1 gap-2 rounded-2xl px-8 text-xs font-black uppercase tracking-widest shadow-xl shadow-accent/20 transition-all hover:shadow-accent/40 md:flex-none"
        >
          <Plus size={18} strokeWidth={3} />
          {tripHeaderText.createTrip}
        </Button>
      </motion.div>
    </div>
  );
}
