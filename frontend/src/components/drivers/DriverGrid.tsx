import { motion } from "framer-motion";
import { BrainCircuit, Edit2, Star, Trash2 } from "lucide-react";

import { Driver } from "../../types";
import { driverGridText } from "../../resources/tr/drivers";
import { cn } from "../../lib/utils";

interface DriverGridProps {
  drivers: Driver[];
  onEdit: (driver: Driver) => void;
  onDelete: (driver: Driver) => void;
  onPerformanceClick: (driver: Driver) => void;
}

export function DriverGrid({
  drivers,
  onEdit,
  onDelete,
  onPerformanceClick,
}: DriverGridProps) {
  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {drivers.map((driver, index) => (
        <motion.div
          key={driver.id}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.05 }}
          className="flex flex-col rounded-card border border-border bg-surface p-6 shadow-sm transition-all hover:border-accent hover:shadow-md"
        >
          <div className="mb-6 flex items-start justify-between">
            <div className="flex h-12 w-12 items-center justify-center rounded-card border border-border bg-elevated text-xl font-bold text-accent shadow-sm">
              {driver.ad_soyad[0]}
            </div>
            <div
              className={cn(
                "flex items-center gap-1.5 rounded-lg border px-2 py-0.5 text-[10px] font-bold uppercase tracking-tight",
                driver.aktif
                  ? "border-success/20 bg-success/10 text-success"
                  : "border-border bg-elevated text-secondary",
              )}
            >
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  driver.aktif
                    ? "bg-success shadow-[0_0_8px_rgba(34,197,94,0.3)]"
                    : "bg-border",
                )}
              />
              {driver.aktif
                ? driverGridText.status.active
                : driverGridText.status.inactive}
            </div>
          </div>
          <h4 className="mb-1 text-base font-bold text-primary">
            {driver.ad_soyad}
          </h4>
          <p className="mb-4 text-xs font-medium text-secondary">
            {driverGridText.licenseSuffix(driver.ehliyet_sinifi)}
          </p>
          <div className="mt-auto flex items-center justify-between border-t border-border pt-4">
            <div className="flex items-center gap-0.5">
              {[...Array(5)].map((_, index) => (
                <Star
                  key={index}
                  className={cn(
                    "h-3.5 w-3.5",
                    index < (driver.score || 0)
                      ? "fill-warning text-warning"
                      : "text-border",
                  )}
                />
              ))}
            </div>
            <div className="flex gap-1">
              <button
                onClick={() => onPerformanceClick(driver)}
                className="rounded-lg p-2 text-secondary transition-colors hover:bg-info/10 hover:text-info focus:outline-none"
                title={driverGridText.actions.aiAnalysis}
              >
                <BrainCircuit className="h-4 w-4" />
              </button>
              <button
                onClick={() => onEdit(driver)}
                className="rounded-lg p-2 text-secondary transition-colors hover:bg-accent/10 hover:text-accent focus:outline-none"
                title={driverGridText.actions.edit}
              >
                <Edit2 className="h-4 w-4" />
              </button>
              <button
                onClick={() => onDelete(driver)}
                className="rounded-lg p-2 text-secondary transition-colors hover:bg-danger/10 hover:text-danger focus:outline-none"
                title={driverGridText.actions.delete}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        </motion.div>
      ))}
    </div>
  );
}
