import { AlertTriangle, Truck, User2, X } from "lucide-react";
import { cn } from "../../lib/utils";
import type {
  DriverSuggestion,
  VehicleSuggestion,
} from "../../api/trip-planner";
import { useTripPlannerResources } from "../../resources/useResources";

// Plan §4 — ağırlıklar sabit (TripPlannerEngine.ARAC_WEIGHTS / SOFOR_WEIGHTS ile aynı).
const VEHICLE_WEIGHTS = {
  fuel: 0.4,
  route_history: 0.25,
  vehicle_health: 0.2,
  availability: 0.15,
} as const;

const DRIVER_WEIGHTS = {
  route_type_perf: 0.5,
  overall_hybrid: 0.3,
  availability: 0.2,
} as const;

interface ScoreBarProps {
  label: string;
  value: number; // 0..1
  weight: number; // 0..1
}

interface XaiPanelProps {
  /** Açık item; null ise panel kapalı. */
  item: VehicleSuggestion | DriverSuggestion | null;
  /** Item türü — discriminator için (zaten tipte çıkarılabilir ama explicit). */
  kind: "vehicle" | "driver" | null;
  onClose: () => void;
}

export function PlanWizardXaiPanel({ item, kind, onClose }: XaiPanelProps) {
  const { tripPlannerText } = useTripPlannerResources();
  function ScoreBar({ label, value, weight }: ScoreBarProps) {
    const pct = Math.max(0, Math.min(1, value)) * 100;
    return (
      <div>
        <div className="mb-1 flex items-center justify-between text-[11px]">
          <span className="text-secondary">{label}</span>
          <span className="font-mono text-tertiary tabular-nums">
            <span className="font-semibold text-primary">
              {value.toFixed(2)}
            </span>
            <span className="ml-2 text-[10px]">
              {(weight * 100).toFixed(0)}% {tripPlannerText.xai.weightSuffix}
            </span>
          </span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-elevated">
          <div
            className={cn(
              "h-full transition-all",
              value >= 0.75
                ? "bg-success"
                : value >= 0.5
                  ? "bg-warning"
                  : "bg-danger/70",
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    );
  }
  if (!item || !kind) return null;

  const isVehicle = kind === "vehicle";
  const vehicle = isVehicle ? (item as VehicleSuggestion) : null;
  const driver = !isVehicle ? (item as DriverSuggestion) : null;
  const heading = vehicle ? vehicle.plaka : driver!.ad_soyad;
  const Icon = isVehicle ? Truck : User2;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-start justify-end bg-black/40 p-0 backdrop-blur-sm sm:items-center sm:p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="relative flex h-full w-full max-w-md flex-col overflow-hidden border-l border-border bg-surface shadow-2xl sm:h-auto sm:max-h-[90vh] sm:rounded-modal sm:border"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={tripPlannerText.xai.title}
      >
        <div className="flex items-start justify-between gap-2 border-b border-border bg-elevated/40 p-4">
          <div className="flex items-start gap-2">
            <Icon className="mt-0.5 h-5 w-5 text-accent" />
            <div>
              <h3 className="text-sm font-semibold text-primary">{heading}</h3>
              <p className="text-[11px] text-secondary">
                {tripPlannerText.xai.title} —{" "}
                {isVehicle
                  ? tripPlannerText.xai.vehicleSubtitle
                  : tripPlannerText.xai.driverSubtitle}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={tripPlannerText.xai.close}
            className="rounded-full p-1.5 text-secondary transition-colors hover:bg-elevated hover:text-primary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="custom-scrollbar flex-1 space-y-4 overflow-y-auto p-4">
          {/* Toplam skor */}
          <div className="rounded-card border border-accent/30 bg-accent/5 px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-secondary">
                {tripPlannerText.xai.totalScore}
              </span>
              <span className="font-mono text-lg font-bold tabular-nums text-accent">
                {item.score.toFixed(2)}
              </span>
            </div>
          </div>

          {/* Alt skorlar */}
          <div className="space-y-3">
            {vehicle ? (
              <>
                <ScoreBar
                  label={tripPlannerText.xai.vehicleFactors.fuel}
                  value={vehicle.fuel_score}
                  weight={VEHICLE_WEIGHTS.fuel}
                />
                <ScoreBar
                  label={tripPlannerText.xai.vehicleFactors.route_history}
                  value={vehicle.route_history_score}
                  weight={VEHICLE_WEIGHTS.route_history}
                />
                <ScoreBar
                  label={tripPlannerText.xai.vehicleFactors.vehicle_health}
                  value={vehicle.vehicle_health_score}
                  weight={VEHICLE_WEIGHTS.vehicle_health}
                />
                <ScoreBar
                  label={tripPlannerText.xai.vehicleFactors.availability}
                  value={vehicle.availability_score}
                  weight={VEHICLE_WEIGHTS.availability}
                />
              </>
            ) : driver ? (
              <>
                <ScoreBar
                  label={tripPlannerText.xai.driverFactors.route_type_perf}
                  value={driver.route_type_perf}
                  weight={DRIVER_WEIGHTS.route_type_perf}
                />
                <ScoreBar
                  label={tripPlannerText.xai.driverFactors.overall_hybrid}
                  value={driver.overall_hybrid}
                  weight={DRIVER_WEIGHTS.overall_hybrid}
                />
                <ScoreBar
                  label={tripPlannerText.xai.driverFactors.availability}
                  value={driver.availability_score}
                  weight={DRIVER_WEIGHTS.availability}
                />
              </>
            ) : null}
          </div>

          {/* Meta bilgiler */}
          <div className="grid grid-cols-2 gap-2 rounded-card border border-border/40 bg-elevated/30 p-3 text-[11px]">
            {vehicle ? (
              <>
                <div>
                  <p className="text-tertiary">
                    {tripPlannerText.xai.meta.predicted}
                  </p>
                  <p className="font-mono tabular-nums font-semibold text-primary">
                    {vehicle.predicted_liters.toFixed(1)} L
                  </p>
                </div>
                <div>
                  <p className="text-tertiary">
                    {tripPlannerText.xai.meta.age}
                  </p>
                  <p className="font-mono tabular-nums font-semibold text-primary">
                    {vehicle.yas}
                  </p>
                </div>
                <div>
                  <p className="text-tertiary">
                    {tripPlannerText.xai.meta.similar}
                  </p>
                  <p className="font-mono tabular-nums font-semibold text-primary">
                    {vehicle.similar_trip_count}
                  </p>
                </div>
              </>
            ) : driver ? (
              <>
                <div>
                  <p className="text-tertiary">
                    {tripPlannerText.xai.meta.routeType}
                  </p>
                  <p className="font-semibold text-primary">
                    {tripPlannerText.routeTypeLabels[driver.route_type]}
                  </p>
                </div>
                <div>
                  <p className="text-tertiary">
                    {tripPlannerText.xai.meta.deviation}
                  </p>
                  <p
                    className={cn(
                      "font-mono tabular-nums font-semibold",
                      driver.deviation_pct < 0
                        ? "text-success"
                        : driver.deviation_pct > 0
                          ? "text-danger"
                          : "text-primary",
                    )}
                  >
                    {driver.deviation_pct > 0 ? "+" : ""}
                    {driver.deviation_pct.toFixed(1)}%
                  </p>
                </div>
              </>
            ) : null}
          </div>

          {/* Sebepler */}
          <div>
            <h4 className="mb-2 text-[10px] font-bold uppercase tracking-widest text-secondary">
              {tripPlannerText.xai.reasonsHeading}
            </h4>
            {(item.reasons ?? []).length === 0 ? (
              <p className="text-[11px] italic text-tertiary">
                {tripPlannerText.xai.noReasons}
              </p>
            ) : (
              <ul className="space-y-1.5">
                {(item.reasons ?? []).map((r, i) => {
                  const isWarning = r.startsWith("⚠");
                  return (
                    <li
                      key={i}
                      className={cn(
                        "flex items-start gap-2 rounded-card border px-2.5 py-1.5 text-[11px]",
                        isWarning
                          ? "border-warning/30 bg-warning/5 text-warning"
                          : "border-border/40 bg-elevated/30 text-primary",
                      )}
                    >
                      {isWarning && (
                        <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                      )}
                      <span>{isWarning ? r.replace(/^⚠\s*/, "") : r}</span>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
