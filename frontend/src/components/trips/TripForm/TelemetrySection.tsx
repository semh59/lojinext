import React from "react";
import { FieldErrors } from "react-hook-form";
import { Navigation } from "lucide-react";

import { tripTelemetrySectionText } from "../../../resources/tr/trips";
import { TripFormData } from "../../../types";
import { cn } from "../../../lib/utils";
import { WeatherAnalysisCard } from "../../weather/WeatherAnalysisCard";

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
      <div className="space-y-4 rounded-[24px] border border-border bg-surface p-6">
        <h4 className="flex items-center gap-2 text-xs font-black uppercase tracking-widest text-secondary">
          <Navigation className="h-4 w-4 text-accent" />
          {tripTelemetrySectionText.heading}
        </h4>
        <WeatherAnalysisCard
          weatherImpact={weatherImpact}
          weatherLoading={weatherLoading}
        />
        {watchedGuzergahId ? (
          <div className="flex items-center justify-between rounded-2xl border border-border bg-base p-5">
            <div className="flex flex-col">
              <span className="mb-1 text-[10px] font-bold uppercase tracking-wider text-secondary">
                {tripTelemetrySectionText.departureLabel}
              </span>
              <span className="text-sm font-black text-primary">
                {watchedCikis}
              </span>
            </div>
            <div className="flex w-full min-w-[80px] flex-col items-center px-4">
              <div className="relative mb-1.5 flex h-1 w-full items-center justify-center rounded-full bg-border">
                <div className="absolute inset-x-8 h-full rounded-full bg-accent/30" />
                <div className="absolute h-2 w-2 rounded-full bg-accent" />
              </div>
              <span
                className={cn(
                  "text-xs font-black tabular-nums tracking-widest transition-colors",
                  errors.mesafe_km ? "text-danger" : "text-accent",
                )}
              >
                {watchedMesafe} {tripTelemetrySectionText.distanceUnit}
              </span>
              {errors.mesafe_km && (
                <p className="absolute -bottom-6 whitespace-nowrap text-[10px] font-bold text-danger">
                  {tripTelemetrySectionText.distanceErrorTitle}
                </p>
              )}
            </div>
            <div className="flex flex-col items-end">
              <span className="mb-1 text-[10px] font-bold uppercase tracking-wider text-secondary">
                {tripTelemetrySectionText.arrivalLabel}
              </span>
              <span className="text-sm font-black text-primary">
                {watchedVaris}
              </span>
            </div>
          </div>
        ) : (
          <div className="rounded-2xl border-2 border-dashed border-border bg-base py-10 text-center text-xs font-bold uppercase tracking-[0.2em] text-secondary">
            {tripTelemetrySectionText.emptyTitle}
          </div>
        )}
      </div>
    );
  },
);
