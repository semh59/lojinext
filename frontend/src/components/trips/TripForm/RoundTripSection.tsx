import React from "react";
import { UseFormRegister } from "react-hook-form";
import { motion } from "framer-motion";
import { ArrowLeftRight } from "lucide-react";

import { tripRoundTripSectionText } from "../../../resources/tr/trips";
import { TripFormData } from "../../../types";
import { Input } from "../../ui/Input";

interface RoundTripSectionProps {
  register: UseFormRegister<TripFormData>;
  prefersReducedMotion: boolean;
  transitionProps: any;
}

export const RoundTripSection: React.FC<RoundTripSectionProps> = React.memo(
  ({ register, prefersReducedMotion, transitionProps }) => {
    return (
      <motion.div
        initial={
          prefersReducedMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 10 }
        }
        animate={{ opacity: 1, y: 0 }}
        transition={transitionProps}
        className="space-y-4 rounded-[24px] border border-warning/30 bg-warning/5 p-6"
      >
        <h4 className="flex items-center gap-2 text-xs font-black uppercase tracking-widest text-warning">
          <ArrowLeftRight className="h-4 w-4" />
          {tripRoundTripSectionText.heading}
        </h4>
        <div className="grid grid-cols-2 gap-6">
          <div className="space-y-1.5">
            <label className="text-[10px] font-bold uppercase tracking-widest text-warning/70">
              {tripRoundTripSectionText.tripNumberLabel}
            </label>
            <Input
              placeholder={tripRoundTripSectionText.tripNumberPlaceholder}
              {...register("return_sefer_no")}
              className="h-12 border-warning/20 bg-elevated text-primary"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-bold uppercase tracking-widest text-warning/70">
              {tripRoundTripSectionText.returnLoadLabel}
            </label>
            <Input
              type="number"
              placeholder={tripRoundTripSectionText.returnLoadPlaceholder}
              {...register("return_net_kg")}
              className="h-12 border-warning/20 bg-elevated text-lg font-black text-primary"
            />
          </div>
        </div>
      </motion.div>
    );
  },
);
