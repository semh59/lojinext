import React, { useMemo } from "react";
import { FieldErrors, UseFormRegister } from "react-hook-form";
import { AlertCircle, ChevronDown, MapPin, Route, X } from "lucide-react";
import { motion } from "framer-motion";

import { Guzergah, TripFormData } from "../../../types";
import { cn } from "../../../lib/utils";
import { useTripsResources } from "../../../resources/useResources";

interface RouteSelectorProps {
  register: UseFormRegister<TripFormData>;
  errors: FieldErrors<TripFormData>;
  routes: Guzergah[];
  watchedGuzergahId: number | string;
  isReadOnly?: boolean;
}

export const RouteSelector: React.FC<RouteSelectorProps> = React.memo(
  ({ register, errors, routes, watchedGuzergahId, isReadOnly = false }) => {
    const { tripRouteSelectorText } = useTripsResources();
    const selectedRoute = useMemo(
      () => routes.find((route) => route.id === Number(watchedGuzergahId)),
      [routes, watchedGuzergahId],
    );

    return (
      <div className="glass group relative overflow-hidden rounded-[28px] border-border/40 p-6 transition-all hover:border-accent/20">
        <div className="mb-5 flex items-center justify-between">
          <label className="flex items-center gap-2 px-1 text-[10px] font-black uppercase tracking-[0.2em] text-accent">
            <Route size={14} strokeWidth={3} />
            {tripRouteSelectorText.heading}
          </label>
          {selectedRoute && (
            <span className="rounded-lg border border-border/40 bg-elevated px-2 py-1 text-[10px] font-black uppercase tracking-tighter text-tertiary tabular-nums">
              {selectedRoute.mesafe_km} {tripRouteSelectorText.distanceUnit}
            </span>
          )}
        </div>

        <div className="relative">
          <div className="absolute left-4 top-1/2 z-10 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg bg-accent/5 text-accent/60">
            <MapPin size={18} strokeWidth={2.5} />
          </div>
          <select
            {...register("guzergah_id")}
            disabled={isReadOnly}
            className={cn(
              "h-14 w-full appearance-none rounded-xl border bg-transparent pl-14 text-sm font-black text-primary outline-none transition-all",
              errors.guzergah_id
                ? "border-danger ring-2 ring-danger/10"
                : "border-border/60 shadow-inner hover:border-accent/40 focus:border-accent focus:ring-4 focus:ring-accent/5",
            )}
          >
            <option value="" className="bg-surface font-bold text-tertiary">
              {tripRouteSelectorText.emptyOption}
            </option>
            {routes?.map((route) => (
              <option
                key={route.id}
                value={route.id}
                className={cn(
                  "text-sm font-bold",
                  !route.aktif
                    ? "bg-danger text-white"
                    : "bg-surface text-primary",
                )}
              >
                {route.ad || `${route.cikis_yeri} - ${route.varis_yeri}`}{" "}
                {!route.aktif && tripRouteSelectorText.inactiveTag}
              </option>
            ))}
          </select>
          <div className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-tertiary opacity-40">
            <ChevronDown size={20} strokeWidth={3} />
          </div>
        </div>

        {errors.guzergah_id && (
          <motion.p
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-3 flex items-center gap-1.5 px-1 text-[10px] font-black uppercase tracking-wider text-danger"
          >
            <AlertCircle size={14} strokeWidth={3} />
            {String(
              errors.guzergah_id.message ??
                tripRouteSelectorText.requiredErrorFallback,
            )}
          </motion.p>
        )}

        {selectedRoute && !selectedRoute.aktif && (
          <div className="mt-4 flex items-center gap-3 rounded-2xl border border-danger/20 bg-danger/5 p-4">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-danger/10 text-danger">
              <X size={18} strokeWidth={3} />
            </div>
            <p className="text-[10px] font-black uppercase leading-tight tracking-tight text-danger">
              {tripRouteSelectorText.inactiveWarning}
            </p>
          </div>
        )}
      </div>
    );
  },
);
