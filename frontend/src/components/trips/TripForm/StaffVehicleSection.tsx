import React from "react";
import { FieldErrors, UseFormRegister } from "react-hook-form";
import { AlertCircle, ChevronDown, HardDrive, Truck, User } from "lucide-react";

import { Dorse, Driver, TripFormData, Vehicle } from "../../../types";
import { cn } from "../../../lib/utils";
import { useTripsResources } from "../../../resources/useResources";

interface StaffVehicleSectionProps {
  register: UseFormRegister<TripFormData>;
  errors: FieldErrors<TripFormData>;
  vehicles: Vehicle[];
  drivers: Driver[];
  trailers: Dorse[];
  isReadOnly?: boolean;
}

export const StaffVehicleSection: React.FC<StaffVehicleSectionProps> =
  React.memo(
    ({ register, errors, vehicles, drivers, trailers, isReadOnly = false }) => {
      const { tripStaffVehicleSectionText } = useTripsResources();
      return (
        <div className="glass space-y-6 rounded-[28px] border-border/40 p-6">
          <h4 className="mb-2 flex items-center gap-2 px-1 text-[10px] font-black uppercase tracking-[0.2em] text-accent">
            <Truck size={14} strokeWidth={3} />
            {tripStaffVehicleSectionText.heading}
          </h4>

          <div className="space-y-5">
            <div className="space-y-2">
              <label className="px-1 text-[10px] font-black uppercase tracking-widest text-tertiary">
                {tripStaffVehicleSectionText.vehicleLabel}
              </label>
              <div className="relative">
                <div className="absolute left-4 top-1/2 z-10 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg bg-accent/5 text-accent/60">
                  <Truck size={16} strokeWidth={2.5} />
                </div>
                <select
                  {...register("arac_id")}
                  disabled={isReadOnly}
                  className={cn(
                    "h-14 w-full appearance-none rounded-xl border bg-transparent pl-14 text-sm font-black outline-none transition-all",
                    errors.arac_id
                      ? "border-danger ring-2 ring-danger/10"
                      : "border-border/60 hover:border-accent/40 focus:border-accent focus:ring-4 focus:ring-accent/5",
                  )}
                >
                  <option value="0" className="bg-surface font-bold">
                    {tripStaffVehicleSectionText.vehiclePlaceholder}
                  </option>
                  {vehicles?.map((vehicle) => (
                    <option
                      key={vehicle.id}
                      value={vehicle.id}
                      className="bg-surface font-bold text-primary"
                    >
                      {vehicle.plaka}
                    </option>
                  ))}
                </select>
                <div className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-tertiary opacity-40">
                  <ChevronDown size={18} strokeWidth={3} />
                </div>
              </div>
              {errors.arac_id && (
                <p className="mt-1 flex items-center gap-1 px-1 text-[10px] font-black uppercase tracking-wider text-danger">
                  <AlertCircle size={12} strokeWidth={3} />
                  {String(errors.arac_id.message ?? "")}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <label className="px-1 text-[10px] font-black uppercase tracking-widest text-tertiary">
                {tripStaffVehicleSectionText.trailerLabel}
              </label>
              <div className="relative">
                <div className="absolute left-4 top-1/2 z-10 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg bg-tertiary/5 text-tertiary/60">
                  <HardDrive size={16} strokeWidth={2.5} />
                </div>
                <select
                  {...register("dorse_id")}
                  disabled={isReadOnly}
                  className="h-14 w-full appearance-none rounded-xl border border-border/60 bg-transparent pl-14 text-sm font-black text-primary outline-none transition-all hover:border-accent/40 focus:border-accent focus:ring-4 focus:ring-accent/5"
                >
                  <option value="0" className="bg-surface font-bold">
                    {tripStaffVehicleSectionText.trailerPlaceholder}
                  </option>
                  {trailers?.map((trailer) => (
                    <option
                      key={trailer.id}
                      value={trailer.id}
                      className="bg-surface font-bold text-primary"
                    >
                      {trailer.plaka}
                    </option>
                  ))}
                </select>
                <div className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-tertiary opacity-40">
                  <ChevronDown size={18} strokeWidth={3} />
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <label className="px-1 text-[10px] font-black uppercase tracking-widest text-tertiary">
                {tripStaffVehicleSectionText.driverLabel}
              </label>
              <div className="relative">
                <div className="absolute left-4 top-1/2 z-10 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg bg-accent/5 text-accent/60">
                  <User size={16} strokeWidth={2.5} />
                </div>
                <select
                  {...register("sofor_id")}
                  disabled={isReadOnly}
                  className={cn(
                    "h-14 w-full appearance-none rounded-xl border bg-transparent pl-14 text-sm font-black outline-none transition-all",
                    errors.sofor_id
                      ? "border-danger ring-2 ring-danger/10"
                      : "border-border/60 hover:border-accent/40 focus:border-accent focus:ring-4 focus:ring-accent/5",
                  )}
                >
                  <option value="0" className="bg-surface font-bold">
                    {tripStaffVehicleSectionText.driverPlaceholder}
                  </option>
                  {drivers?.map((driver) => (
                    <option
                      key={driver.id}
                      value={driver.id}
                      className="bg-surface font-bold text-primary"
                    >
                      {driver.ad_soyad}
                    </option>
                  ))}
                </select>
                <div className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-tertiary opacity-40">
                  <ChevronDown size={18} strokeWidth={3} />
                </div>
              </div>
              {errors.sofor_id && (
                <p className="mt-1 flex items-center gap-1 px-1 text-[10px] font-black uppercase tracking-wider text-danger">
                  <AlertCircle size={12} strokeWidth={3} />
                  {String(errors.sofor_id.message ?? "")}
                </p>
              )}
            </div>
          </div>
        </div>
      );
    },
  );
