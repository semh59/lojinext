import { useState } from "react";
import {
  AlertTriangle,
  Cloud,
  CloudRain,
  Loader2,
  Map,
  Sparkles,
} from "lucide-react";
import { cn } from "../../lib/utils";
import {
  type DriverSuggestion,
  type PlanWizardRequestPayload,
  type PlanWizardResponse,
  type RiskLabel,
  type VehicleSuggestion,
} from "../../api/trip-planner";
import { usePlanWizard } from "../../hooks/usePlanWizard";
import { PlanWizardCard } from "./PlanWizardCard";
import { PlanWizardXaiPanel } from "./PlanWizardXaiPanel";
import { useTripPlannerResources } from "../../resources/useResources";

export interface PlanWizardSelection {
  arac_id: number;
  sofor_id: number;
  plaka: string;
  sofor_adi: string;
}

interface PlanWizardStepProps {
  /** Wizard tetiklemek için gereken minimum veri.
   *  Eksikse buton disabled olur. */
  payload: PlanWizardRequestPayload | null;
  onSelectAndContinue: (sel: PlanWizardSelection) => void;
  onOpenXai?: (item: VehicleSuggestion | DriverSuggestion) => void;
}

const RISK_STYLE: Record<RiskLabel, string> = {
  high: "bg-danger/10 text-danger border-danger/30",
  medium: "bg-warning/10 text-warning border-warning/30",
  low: "bg-success/10 text-success border-success/30",
  unknown: "bg-elevated text-secondary border-border",
};

export function PlanWizardStep({
  payload,
  onSelectAndContinue,
  onOpenXai,
}: PlanWizardStepProps) {
  const { tripPlannerText } = useTripPlannerResources();
  function RiskBadge({ label }: { label: RiskLabel }) {
    const Icon = label === "high" ? CloudRain : Cloud;
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider",
          RISK_STYLE[label],
        )}
      >
        <Icon className="h-3 w-3" />
        {tripPlannerText.risk[label]}
      </span>
    );
  }
  function RouteTypeBadge({
    routeType,
  }: {
    routeType: PlanWizardResponse["route_type"];
  }) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-border bg-elevated px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-secondary">
        <Map className="h-3 w-3" />
        {tripPlannerText.routeTypeLabels[routeType]}
      </span>
    );
  }
  const mutation = usePlanWizard();
  const [selectedVehicle, setSelectedVehicle] =
    useState<VehicleSuggestion | null>(null);
  const [selectedDriver, setSelectedDriver] = useState<DriverSuggestion | null>(
    null,
  );
  const [xaiTarget, setXaiTarget] = useState<{
    item: VehicleSuggestion | DriverSuggestion;
    kind: "vehicle" | "driver";
  } | null>(null);

  const handleOpenXai = (
    item: VehicleSuggestion | DriverSuggestion,
    kind: "vehicle" | "driver",
  ) => {
    setXaiTarget({ item, kind });
    onOpenXai?.(item);
  };

  const canFetch =
    payload !== null && payload.mesafe_km > 0 && Boolean(payload.tarih);

  const handleFetch = () => {
    if (!payload) return;
    setSelectedVehicle(null);
    setSelectedDriver(null);
    mutation.mutate(payload);
  };

  const handleContinue = () => {
    if (!selectedVehicle || !selectedDriver) return;
    onSelectAndContinue({
      arac_id: selectedVehicle.arac_id,
      sofor_id: selectedDriver.sofor_id,
      plaka: selectedVehicle.plaka,
      sofor_adi: selectedDriver.ad_soyad,
    });
  };

  const errorMessage = (() => {
    if (!mutation.error) return null;
    const err = mutation.error as unknown as {
      response?: { status?: number; data?: { error?: { message?: string } } };
    };
    const status = err?.response?.status;
    if (status === 503) return tripPlannerText.errors.flagOff;
    if (status === 403) return tripPlannerText.errors.forbidden;
    return err?.response?.data?.error?.message ?? tripPlannerText.errors.fetch;
  })();

  const result = mutation.data;

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2 rounded-modal border border-border bg-elevated/40 p-3">
        <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-primary">
            {tripPlannerText.title}
          </h3>
          <p className="mt-0.5 text-xs text-secondary">
            {tripPlannerText.intro}
          </p>
        </div>
        <button
          type="button"
          onClick={handleFetch}
          disabled={!canFetch || mutation.isPending}
          className={cn(
            "inline-flex items-center gap-2 rounded-card bg-accent px-3 py-2 text-xs font-semibold text-white shadow-sm transition-all",
            "hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50",
          )}
        >
          {mutation.isPending && <Loader2 className="h-3 w-3 animate-spin" />}
          {mutation.isError
            ? tripPlannerText.retryButton
            : tripPlannerText.fetchButton}
        </button>
      </div>

      {!canFetch && !result && (
        <div className="flex items-center gap-2 rounded-card border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-warning">
          <AlertTriangle className="h-3.5 w-3.5" />
          {tripPlannerText.errors.missingRoute}
        </div>
      )}

      {mutation.isPending && (
        <div className="space-y-2">
          <div className="h-20 animate-pulse rounded-modal border border-border bg-elevated/40" />
          <div className="h-20 animate-pulse rounded-modal border border-border bg-elevated/40" />
        </div>
      )}

      {errorMessage && (
        <div className="flex items-center gap-2 rounded-card border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger">
          <AlertTriangle className="h-3.5 w-3.5" />
          {errorMessage}
        </div>
      )}

      {result && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <RiskBadge label={result.risk_label} />
            <RouteTypeBadge routeType={result.route_type} />
            <span className="ml-auto text-[10px] text-tertiary">
              x{result.weather_impact.toFixed(2)}
            </span>
          </div>

          {result.vehicles.length === 0 && result.drivers.length === 0 ? (
            <div className="flex items-center gap-2 rounded-card border border-warning/30 bg-warning/5 px-3 py-3 text-xs text-warning">
              <AlertTriangle className="h-3.5 w-3.5" />
              {tripPlannerText.errors.empty}
            </div>
          ) : (
            <>
              <section className="space-y-2">
                <h4 className="text-[10px] font-bold uppercase tracking-widest text-secondary">
                  {tripPlannerText.sections.vehicles}
                </h4>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {result.vehicles.map((v) => (
                    <PlanWizardCard
                      key={v.arac_id}
                      kind="vehicle"
                      data={v}
                      selected={selectedVehicle?.arac_id === v.arac_id}
                      onSelect={() => setSelectedVehicle(v)}
                      onOpenXai={() => handleOpenXai(v, "vehicle")}
                    />
                  ))}
                </div>
              </section>

              <section className="space-y-2">
                <h4 className="text-[10px] font-bold uppercase tracking-widest text-secondary">
                  {tripPlannerText.sections.drivers}
                </h4>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {result.drivers.map((d) => (
                    <PlanWizardCard
                      key={d.sofor_id}
                      kind="driver"
                      data={d}
                      selected={selectedDriver?.sofor_id === d.sofor_id}
                      onSelect={() => setSelectedDriver(d)}
                      onOpenXai={() => handleOpenXai(d, "driver")}
                    />
                  ))}
                </div>
              </section>

              <div className="flex items-center justify-between gap-3 border-t border-border/40 pt-3">
                <p className="text-[11px] text-secondary">
                  {tripPlannerText.confirmSelection}
                </p>
                <button
                  type="button"
                  onClick={handleContinue}
                  disabled={!selectedVehicle || !selectedDriver}
                  className="inline-flex items-center gap-2 rounded-card bg-accent px-3 py-2 text-xs font-semibold text-white shadow-sm transition-all hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {tripPlannerText.selectAndContinue}
                </button>
              </div>
            </>
          )}
        </>
      )}

      <PlanWizardXaiPanel
        item={xaiTarget?.item ?? null}
        kind={xaiTarget?.kind ?? null}
        onClose={() => setXaiTarget(null)}
      />
    </div>
  );
}
