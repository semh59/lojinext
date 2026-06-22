import React from "react";
import { ChevronDown, Settings } from "lucide-react";
import { UseFormRegister } from "react-hook-form";

import { tripFormModalText } from "../../resources/tr/trips";
import {
  TRIP_STATUS_IPTAL,
  TRIP_STATUS_PLANLANDI,
  TRIP_STATUS_TAMAMLANDI,
  normalizeTripStatus,
} from "../../lib/trip-status";
import { Trip, TripFormData } from "../../types";

// ---------------------------------------------------------------------------
// KilometreYakitSection
// ---------------------------------------------------------------------------

interface KilometreYakitSectionProps {
  register: UseFormRegister<TripFormData>;
}

export const KilometreYakitSection: React.FC<KilometreYakitSectionProps> = ({
  register,
}) => (
  <div className="glass space-y-4 rounded-[28px] border-border/40 p-6">
    <label className="mb-4 flex items-center gap-2 px-1 text-[10px] font-black uppercase tracking-[0.2em] text-tertiary">
      <Settings size={14} strokeWidth={3} />
      Kilometre &amp; Yakıt Takibi
    </label>
    <div className="grid grid-cols-2 gap-4">
      <div className="space-y-1.5">
        <label className="text-[10px] font-bold uppercase tracking-widest text-secondary">
          Başlangıç KM
        </label>
        <div className="relative">
          <input
            type="number"
            min={0}
            {...register("baslangic_km", {
              setValueAs: (v) => (v === "" ? null : Number(v)),
            })}
            placeholder="0"
            className="h-10 w-full rounded-xl border border-border/60 bg-transparent pr-10 pl-4 text-sm font-bold text-primary outline-none transition-all focus:border-accent focus:ring-4 focus:ring-accent/5"
          />
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-bold text-tertiary">
            km
          </span>
        </div>
      </div>
      <div className="space-y-1.5">
        <label className="text-[10px] font-bold uppercase tracking-widest text-secondary">
          Bitiş KM
        </label>
        <div className="relative">
          <input
            type="number"
            min={0}
            {...register("bitis_km", {
              setValueAs: (v) => (v === "" ? null : Number(v)),
            })}
            placeholder="0"
            className="h-10 w-full rounded-xl border border-border/60 bg-transparent pr-10 pl-4 text-sm font-bold text-primary outline-none transition-all focus:border-accent focus:ring-4 focus:ring-accent/5"
          />
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-bold text-tertiary">
            km
          </span>
        </div>
      </div>
      <div className="space-y-1.5">
        <label className="text-[10px] font-bold uppercase tracking-widest text-secondary">
          Dağıtılan Yakıt
        </label>
        <div className="relative">
          <input
            type="number"
            step="0.1"
            min={0}
            {...register("dagitilan_yakit", {
              setValueAs: (v) => (v === "" ? null : Number(v)),
            })}
            placeholder="0.0"
            className="h-10 w-full rounded-xl border border-border/60 bg-transparent pr-8 pl-4 text-sm font-bold text-primary outline-none transition-all focus:border-accent focus:ring-4 focus:ring-accent/5"
          />
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-bold text-tertiary">
            L
          </span>
        </div>
      </div>
      <div className="space-y-1.5">
        <label className="text-[10px] font-bold uppercase tracking-widest text-secondary">
          Gerçek Tüketim
        </label>
        <div className="relative">
          <input
            type="number"
            step="0.1"
            min={0}
            {...register("tuketim", {
              setValueAs: (v) => (v === "" ? null : Number(v)),
            })}
            placeholder="0.0"
            className="h-10 w-full rounded-xl border border-border/60 bg-transparent pr-8 pl-4 text-sm font-bold text-primary outline-none transition-all focus:border-accent focus:ring-4 focus:ring-accent/5"
          />
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-bold text-tertiary">
            L
          </span>
        </div>
      </div>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// TripStatusSection
// ---------------------------------------------------------------------------

interface TripStatusSectionProps {
  register: UseFormRegister<TripFormData>;
  initialData: Trip | null;
}

export const TripStatusSection: React.FC<TripStatusSectionProps> = ({
  register,
  initialData,
}) => (
  <div className="glass space-y-4 rounded-[28px] border-border/40 p-6">
    <label className="mb-2 flex items-center gap-2 px-1 text-[10px] font-black uppercase tracking-[0.2em] text-tertiary">
      <Settings size={14} strokeWidth={3} />
      {tripFormModalText.statusLabel}
    </label>
    <div className="relative">
      <select
        {...register("durum")}
        className="h-14 w-full appearance-none rounded-xl border border-border/60 bg-transparent px-4 text-sm font-black text-primary outline-none transition-all hover:border-accent/40 focus:border-accent focus:ring-4 focus:ring-accent/5"
      >
        <option value={TRIP_STATUS_PLANLANDI} className="bg-surface font-bold">
          {TRIP_STATUS_PLANLANDI}
        </option>
        <option value={TRIP_STATUS_TAMAMLANDI} className="bg-surface font-bold">
          {TRIP_STATUS_TAMAMLANDI}
        </option>
        {normalizeTripStatus(initialData?.durum) === TRIP_STATUS_IPTAL && (
          <option value={TRIP_STATUS_IPTAL} className="bg-surface font-bold">
            {TRIP_STATUS_IPTAL}
          </option>
        )}
      </select>
      <div className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-tertiary opacity-40">
        <ChevronDown size={20} strokeWidth={3} />
      </div>
    </div>
  </div>
);
