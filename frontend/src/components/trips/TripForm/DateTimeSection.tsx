import React from "react";
import { FieldErrors, UseFormRegister } from "react-hook-form";
import { AlertCircle, Calendar, Clock, Hash } from "lucide-react";

import { TripFormData } from "../../../types";
import { Input } from "../../ui/Input";
import { useTripsResources } from "../../../resources/useResources";

interface DateTimeSectionProps {
  register: UseFormRegister<TripFormData>;
  errors: FieldErrors<TripFormData>;
  isReadOnly?: boolean;
}

export const DateTimeSection: React.FC<DateTimeSectionProps> = React.memo(
  ({ register, errors, isReadOnly = false }) => {
    const { tripDateTimeSectionText } = useTripsResources();
    return (
      <div className="glass space-y-6 rounded-[28px] border-border/40 p-6">
        <h4 className="mb-2 flex items-center gap-2 px-1 text-[10px] font-black uppercase tracking-[0.2em] text-accent">
          <Clock size={14} strokeWidth={3} />
          {tripDateTimeSectionText.heading}
        </h4>

        <div className="grid grid-cols-2 gap-5">
          <div className="space-y-2">
            <label className="px-1 text-[10px] font-black uppercase tracking-widest text-tertiary">
              {tripDateTimeSectionText.dateLabel}
            </label>
            <div className="relative">
              <Calendar
                size={14}
                className="absolute left-4 top-1/2 z-10 -translate-y-1/2 text-accent/60"
              />
              <Input
                type="date"
                {...register("tarih")}
                disabled={isReadOnly}
                error={!!errors.tarih}
                className="h-14 rounded-xl border-border/60 bg-transparent pl-11 text-sm font-black text-primary shadow-inner transition-all focus:border-accent focus:ring-4 focus:ring-accent/5"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="px-1 text-[10px] font-black uppercase tracking-widest text-tertiary">
              {tripDateTimeSectionText.timeLabel}
            </label>
            <div className="relative">
              <Clock
                size={14}
                className="absolute left-4 top-1/2 z-10 -translate-y-1/2 text-accent/60"
              />
              <Input
                type="time"
                {...register("saat")}
                disabled={isReadOnly}
                error={!!errors.saat}
                className="h-14 rounded-xl border-border/60 bg-transparent pl-11 text-sm font-black text-primary shadow-inner transition-all focus:border-accent focus:ring-4 focus:ring-accent/5"
              />
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <label className="px-1 text-[10px] font-black uppercase tracking-widest text-tertiary">
            {tripDateTimeSectionText.referenceLabel}
          </label>
          <div className="relative">
            <Hash
              size={14}
              className="absolute left-4 top-1/2 z-10 -translate-y-1/2 text-tertiary/60"
            />
            <Input
              placeholder={tripDateTimeSectionText.referencePlaceholder}
              {...register("sefer_no")}
              disabled={isReadOnly}
              error={!!errors.sefer_no}
              autoComplete="off"
              className="h-14 rounded-xl border-border/60 bg-transparent pl-11 text-sm font-black text-primary shadow-inner transition-all placeholder:text-tertiary/40 focus:border-accent focus:ring-4 focus:ring-accent/5"
            />
          </div>
          {errors.sefer_no && (
            <p className="mt-1 flex items-center gap-1 px-1 text-[10px] font-black uppercase tracking-wider text-danger">
              <AlertCircle size={12} strokeWidth={3} />
              {String(errors.sefer_no.message ?? "")}
            </p>
          )}
        </div>
      </div>
    );
  },
);
