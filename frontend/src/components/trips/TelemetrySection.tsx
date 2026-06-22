import React from "react";
import { FieldErrors } from "react-hook-form";
import { Activity, AlertCircle, MapPin, Navigation, Route } from "lucide-react";

import { tripTelemetrySectionText } from "../../resources/tr/trips";
import { TripFormData } from "../../types";
import { cn } from "../../lib/utils";
import { WeatherAnalysisCard } from "../weather/WeatherAnalysisCard";

interface TelemetrySectionProps {
  watchedGuzergahId: number | string;
  watchedCikis: string;
  watchedVaris: string;
  watchedMesafe: number;
  weatherImpact: number | null;
  weatherLoading: boolean;
  errors: FieldErrors<TripFormData>;
}

export const TelemetrySection: React.FC<TelemetrySectionProps> = React.memo(
  ({
    watchedGuzergahId,
    watchedCikis,
    watchedVaris,
    watchedMesafe,
    weatherImpact,
    weatherLoading,
    errors,
  }) => {
    return (
      <div className="glass relative space-y-5 overflow-hidden rounded-[28px] border-border/40 p-6">
        <h4 className="mb-2 flex items-center gap-2 px-1 text-[10px] font-black uppercase tracking-[0.2em] text-accent">
          <Activity size={14} strokeWidth={3} />
          {tripTelemetrySectionText.heading}
        </h4>

        <WeatherAnalysisCard
          weatherImpact={weatherImpact}
          weatherLoading={weatherLoading}
        />

        {watchedGuzergahId ? (
          <div className="group relative flex flex-col gap-6 rounded-[24px] border border-border/40 bg-elevated p-6 transition-all hover:bg-surface">
            <div className="flex items-start justify-between gap-4">
              <div className="flex flex-1 flex-col gap-1.5">
                <span className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-widest text-tertiary opacity-60">
                  <MapPin size={10} />
                  {tripTelemetrySectionText.departureLabel}
                </span>
                <span className="text-sm font-black uppercase leading-tight tracking-tight text-primary">
                  {watchedCikis}
                </span>
              </div>

              <div className="flex flex-1 flex-col gap-1.5 text-right">
                <span className="flex items-center justify-end gap-1.5 text-[9px] font-black uppercase tracking-widest text-tertiary opacity-60">
                  {tripTelemetrySectionText.arrivalLabel}
                  <MapPin size={10} />
                </span>
                <span className="text-sm font-black uppercase leading-tight tracking-tight text-primary">
                  {watchedVaris}
                </span>
              </div>
            </div>

            <div className="relative flex flex-col items-center py-4">
              <div className="h-[2px] w-full rounded-full bg-border/40" />
              <div className="absolute left-1/2 top-1/2 flex h-8 w-8 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-accent/20 bg-surface text-accent shadow-[0_0_20px_rgba(var(--accent-rgb),0.1)]">
                <Navigation size={14} className="rotate-90" />
              </div>

              <div
                className={cn(
                  "mt-6 rounded-full border px-4 py-1.5 text-[11px] font-black tabular-nums tracking-widest shadow-lg",
                  errors.mesafe_km
                    ? "border-danger bg-danger/10 text-danger shadow-danger/5"
                    : "border-accent/20 bg-accent/5 text-accent shadow-accent/5",
                )}
              >
                {watchedMesafe}{" "}
                <span className="text-[9px] opacity-60">
                  {tripTelemetrySectionText.distanceUnit}
                </span>
              </div>
            </div>

            {errors.mesafe_km && (
              <div className="animate-shake flex items-center gap-1.5 rounded-xl border border-danger/10 bg-danger/5 p-3 text-danger">
                <AlertCircle size={14} strokeWidth={3} />
                <span className="text-[10px] font-black uppercase tracking-widest">
                  {tripTelemetrySectionText.distanceErrorTitle}
                </span>
              </div>
            )}
          </div>
        ) : (
          <div className="group flex flex-col items-center justify-center rounded-[28px] border-2 border-dashed border-border/40 bg-elevated px-6 py-12 transition-all hover:border-accent/20 hover:bg-surface">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-border/20 text-tertiary transition-all duration-500 group-hover:scale-110 group-hover:bg-accent/5 group-hover:text-accent/40">
              <Route size={24} strokeWidth={1.5} />
            </div>
            <span className="text-center text-[10px] font-black uppercase tracking-[0.2em] text-tertiary">
              {tripTelemetrySectionText.emptyTitle}
            </span>
            <p className="mt-2 max-w-[180px] text-center text-[9px] font-bold text-tertiary opacity-60">
              {tripTelemetrySectionText.emptyDescription}
            </p>
          </div>
        )}

        <div className="pointer-events-none absolute -bottom-12 -left-12 h-32 w-32 rounded-full bg-accent/5 blur-[50px]" />
      </div>
    );
  },
);
