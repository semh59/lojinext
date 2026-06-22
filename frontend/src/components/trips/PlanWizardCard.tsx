import { AlertTriangle, BadgeCheck, Sparkles, User2 } from "lucide-react";
import { cn } from "../../lib/utils";
import { tripPlannerText } from "../../resources/tr/tripPlanner";
import type {
  DriverSuggestion,
  VehicleSuggestion,
} from "../../api/trip-planner";

type VehicleProps = {
  kind: "vehicle";
  data: VehicleSuggestion;
  selected: boolean;
  onSelect: () => void;
  onOpenXai: () => void;
};

type DriverProps = {
  kind: "driver";
  data: DriverSuggestion;
  selected: boolean;
  onSelect: () => void;
  onOpenXai: () => void;
};

type Props = VehicleProps | DriverProps;

function ScoreBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const tone =
    value >= 0.75
      ? "bg-success/10 text-success border-success/30"
      : value >= 0.5
        ? "bg-warning/10 text-warning border-warning/30"
        : "bg-elevated text-secondary border-border";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold tabular-nums",
        tone,
      )}
    >
      {pct}
    </span>
  );
}

function ColdStartBadge({ kind }: { kind: "vehicle" | "driver" }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-card border border-info/30 bg-info/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-info">
      <Sparkles className="h-2.5 w-2.5" />
      {tripPlannerText.coldStart[kind]}
    </span>
  );
}

export function PlanWizardCard(props: Props) {
  const { data, selected, onSelect, onOpenXai, kind } = props;
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
      className={cn(
        "group relative w-full cursor-pointer rounded-modal border bg-surface p-3 text-left shadow-sm transition-all hover:border-accent/30 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40",
        selected
          ? "border-accent ring-2 ring-accent/30 bg-accent/5"
          : "border-border",
      )}
      aria-pressed={selected}
    >
      <div className="mb-1.5 flex items-start justify-between gap-2">
        {kind === "vehicle" ? (
          <span className="truncate font-mono text-xs font-bold text-primary">
            {data.plaka || "—"}
          </span>
        ) : (
          <span className="flex items-center gap-1 truncate text-xs font-bold text-primary">
            <User2 className="h-3 w-3" />
            {data.ad_soyad || "—"}
          </span>
        )}
        <ScoreBadge value={data.score} />
      </div>

      <div className="mb-2 grid grid-cols-2 gap-1 text-[10px] text-secondary">
        {kind === "vehicle" ? (
          <>
            <span>
              {tripPlannerText.card.predicted}:{" "}
              <span className="font-mono tabular-nums text-primary">
                {data.predicted_liters.toFixed(1)} {tripPlannerText.card.liters}
              </span>
            </span>
            <span>
              {tripPlannerText.card.age}:{" "}
              <span className="font-mono tabular-nums text-primary">
                {data.yas}
              </span>
            </span>
            <span>
              {tripPlannerText.card.similar}:{" "}
              <span className="font-mono tabular-nums text-primary">
                {data.similar_trip_count}
              </span>
            </span>
          </>
        ) : (
          <>
            <span>
              {
                tripPlannerText.routeTypeLabels[
                  data.route_type as keyof typeof tripPlannerText.routeTypeLabels
                ]
              }
              :{" "}
              <span
                className={cn(
                  "font-mono tabular-nums font-semibold",
                  data.deviation_pct < 0
                    ? "text-success"
                    : data.deviation_pct > 0
                      ? "text-danger"
                      : "text-primary",
                )}
              >
                {data.deviation_pct > 0 ? "+" : ""}
                {data.deviation_pct.toFixed(1)}%
              </span>
            </span>
            <span>
              {tripPlannerText.card.score}:{" "}
              <span className="font-mono tabular-nums text-primary">
                {Math.round(data.overall_hybrid * 100)}/100
              </span>
            </span>
          </>
        )}
      </div>

      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          {data.cold_start && <ColdStartBadge kind={kind} />}
          {selected && (
            <span className="inline-flex items-center gap-1 rounded-card border border-accent/30 bg-accent/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-accent">
              <BadgeCheck className="h-2.5 w-2.5" />
              {tripPlannerText.selected}
            </span>
          )}
          {(data.reasons ?? [])[0] && (
            <span className="line-clamp-1 text-[10px] text-tertiary italic">
              {(data.reasons ?? [])[0].startsWith("⚠") && (
                <AlertTriangle className="mr-0.5 inline h-2.5 w-2.5 text-warning" />
              )}
              {(data.reasons ?? [])[0]}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onOpenXai();
          }}
          className="shrink-0 text-[10px] text-info underline hover:text-info/80"
        >
          {tripPlannerText.card.whyButton}
        </button>
      </div>
    </div>
  );
}
