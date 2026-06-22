import React from "react";
import { Scale } from "lucide-react";
import { motion } from "framer-motion";
import { FieldErrors, UseFormRegister } from "react-hook-form";

import { TripFormData } from "../../../types";
import { Input } from "../../ui/Input";
import { useTripsResources } from "../../../resources/useResources";

interface LoadManagementSectionProps {
  register: UseFormRegister<TripFormData>;
  errors: FieldErrors<TripFormData>;
  watchedNetKg: number;
  isReadOnly?: boolean;
}

export const LoadManagementSection: React.FC<LoadManagementSectionProps> =
  React.memo(({ register, errors, watchedNetKg, isReadOnly = false }) => {
    const { tripLoadManagementSectionText } = useTripsResources();
    return (
      <div className="glass relative space-y-6 overflow-hidden rounded-[28px] border-border/40 p-6">
        <h4 className="mb-2 flex items-center gap-2 px-1 text-[10px] font-black uppercase tracking-[0.2em] text-success">
          <Scale size={14} strokeWidth={3} />
          {tripLoadManagementSectionText.heading}
        </h4>

        <div className="grid grid-cols-2 gap-5">
          <div className="space-y-2">
            <label className="px-1 text-[10px] font-black uppercase tracking-widest text-tertiary">
              {tripLoadManagementSectionText.emptyWeightLabel}
            </label>
            <Input
              type="number"
              placeholder="0"
              {...register("bos_agirlik_kg")}
              disabled={isReadOnly}
              error={!!errors.bos_agirlik_kg}
              className="h-14 rounded-xl border-border/60 bg-transparent text-sm font-black text-primary shadow-inner transition-all tabular-nums focus:border-success focus:ring-4 focus:ring-success/5"
            />
          </div>
          <div className="space-y-2">
            <label className="px-1 text-[10px] font-black uppercase tracking-widest text-tertiary">
              {tripLoadManagementSectionText.loadedWeightLabel}
            </label>
            <Input
              type="number"
              placeholder="0"
              {...register("dolu_agirlik_kg")}
              disabled={isReadOnly}
              error={!!errors.dolu_agirlik_kg}
              className="h-14 rounded-xl border-border/60 bg-transparent text-sm font-black text-primary shadow-inner transition-all tabular-nums focus:border-success focus:ring-4 focus:ring-success/5"
            />
          </div>
        </div>

        <div className="-mx-6 -mb-6 mt-6 flex items-center justify-between border-t border-border/20 bg-elevated p-6 pt-6">
          <div className="flex flex-col">
            <span className="text-[10px] font-black uppercase tracking-widest text-tertiary">
              {tripLoadManagementSectionText.summaryTitle}
            </span>
            <span className="mt-1 text-[9px] font-bold italic uppercase tracking-tighter text-success/60">
              {tripLoadManagementSectionText.summarySubtitle}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <motion.span
              key={watchedNetKg}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="text-3xl font-black tracking-tighter text-success tabular-nums"
            >
              {Math.max(0, watchedNetKg).toLocaleString()}
            </motion.span>
            <span className="text-[10px] font-black uppercase tracking-widest text-success/40">
              {tripLoadManagementSectionText.unit}
            </span>
          </div>
        </div>

        <div className="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-success/5 blur-3xl" />
      </div>
    );
  });
