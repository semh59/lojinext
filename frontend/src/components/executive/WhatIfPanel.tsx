import { useState } from "react";
import { AlertCircle, Loader2, Play, Wand2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { useWhatIf } from "@/hooks/useExecutive";
import type { WhatIfRequest, WhatIfScenarioType } from "@/api/executive";
import { useExecutiveResources } from "@/resources/useResources";

interface Props {
  className?: string;
}

export function WhatIfPanel({ className }: Props) {
  const { executiveText } = useExecutiveResources();
  const SCENARIOS: { id: WhatIfScenarioType; label: string }[] = [
    {
      id: "fleet_renewal",
      label: executiveText.whatIf.scenarios.fleet_renewal,
    },
    { id: "training", label: executiveText.whatIf.scenarios.training },
    {
      id: "route_portfolio",
      label: executiveText.whatIf.scenarios.route_portfolio,
    },
  ];
  const t = executiveText.whatIf;
  const [scenario, setScenario] = useState<WhatIfScenarioType>("fleet_renewal");
  // Senaryo input state'leri (default değerler)
  const [maxAge, setMaxAge] = useState(15);
  const [replCost, setReplCost] = useState(2_000_000);
  const [improvementFleet, setImprovementFleet] = useState(15);
  const [improvementTraining, setImprovementTraining] = useState(5);
  const [trainingCost, setTrainingCost] = useState(3000);
  const [dropBottomN, setDropBottomN] = useState(3);

  const mutation = useWhatIf();

  const handleRun = () => {
    let payload: WhatIfRequest;
    if (scenario === "fleet_renewal") {
      payload = {
        scenario_type: "fleet_renewal",
        fleet_renewal: {
          max_age_years: maxAge,
          replacement_cost_per_vehicle_tl: replCost,
          expected_l_100km_improvement_pct: improvementFleet,
        },
      };
    } else if (scenario === "training") {
      payload = {
        scenario_type: "training",
        training: {
          improvement_pct: improvementTraining,
          training_cost_per_driver_tl: trainingCost,
        },
      };
    } else {
      payload = {
        scenario_type: "route_portfolio",
        route_portfolio: { drop_bottom_n: dropBottomN, iterations: 100 },
      };
    }
    mutation.mutate(payload);
  };

  const result = mutation.data;

  return (
    <div
      className={cn(
        "rounded-modal border border-border bg-surface p-6 shadow-sm",
        className,
      )}
    >
      <div className="mb-4 flex items-center gap-2">
        <Wand2 className="h-4 w-4 text-accent" />
        <h3 className="text-xs font-bold uppercase tracking-widest text-secondary">
          {t.title}
        </h3>
      </div>

      {/* Senaryo seçici */}
      <div className="mb-3 flex flex-wrap gap-2">
        {SCENARIOS.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setScenario(s.id)}
            className={cn(
              "rounded-card border px-3 py-1.5 text-xs font-semibold transition-all",
              scenario === s.id
                ? "border-accent bg-accent/10 text-accent"
                : "border-border bg-elevated text-secondary hover:bg-elevated/70",
            )}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* Senaryo input'ları */}
      <div className="mb-3 grid grid-cols-1 gap-3 rounded-card border border-border/40 bg-elevated/30 p-3 sm:grid-cols-3">
        {scenario === "fleet_renewal" && (
          <>
            <NumberInput
              label={t.inputs.maxAgeYears}
              value={maxAge}
              onChange={setMaxAge}
              min={1}
              max={50}
            />
            <NumberInput
              label={t.inputs.replacementCost}
              value={replCost}
              onChange={setReplCost}
              min={100_000}
              step={100_000}
            />
            <NumberInput
              label={t.inputs.improvementPct}
              value={improvementFleet}
              onChange={setImprovementFleet}
              min={1}
              max={50}
            />
          </>
        )}
        {scenario === "training" && (
          <>
            <NumberInput
              label={t.inputs.improvementPct}
              value={improvementTraining}
              onChange={setImprovementTraining}
              min={1}
              max={30}
            />
            <NumberInput
              label={t.inputs.trainingCost}
              value={trainingCost}
              onChange={setTrainingCost}
              min={500}
              step={500}
            />
          </>
        )}
        {scenario === "route_portfolio" && (
          <NumberInput
            label={t.inputs.dropBottomN}
            value={dropBottomN}
            onChange={setDropBottomN}
            min={1}
            max={20}
          />
        )}
        <div className="sm:col-span-3 sm:flex sm:justify-end">
          <button
            type="button"
            onClick={handleRun}
            disabled={mutation.isPending}
            className="inline-flex items-center gap-2 rounded-card bg-accent px-4 py-2 text-xs font-semibold text-white shadow-sm transition-all hover:bg-accent/90 disabled:opacity-50"
          >
            {mutation.isPending ? (
              <>
                <Loader2 className="h-3 w-3 animate-spin" />
                {t.running}
              </>
            ) : (
              <>
                <Play className="h-3 w-3" />
                {t.runButton}
              </>
            )}
          </button>
        </div>
      </div>

      {/* Sonuçlar */}
      {mutation.isError && (
        <div className="flex items-start gap-2 rounded-card border border-danger/30 bg-danger/5 p-3 text-xs text-danger">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {executiveText.errors.loadFailed}
        </div>
      )}

      {result && (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Metric
              label={t.results.yearlySavings}
              value={`₺${result.yearly_savings_tl.toLocaleString("tr-TR")}`}
              highlight
            />
            <Metric
              label={t.results.upfront}
              value={
                result.upfront_cost_tl > 0
                  ? `₺${result.upfront_cost_tl.toLocaleString("tr-TR")}`
                  : "—"
              }
            />
            <Metric
              label={t.results.payback}
              value={
                result.payback_years !== null && result.payback_years > 0
                  ? `${result.payback_years.toFixed(1)} yıl`
                  : "—"
              }
            />
            <Metric
              label={t.results.fiveYearRoi}
              value={`${result.five_year_roi_pct.toFixed(1)}%`}
            />
          </div>

          {result.monte_carlo && (
            <div className="grid grid-cols-3 gap-2 rounded-card border border-border/40 bg-elevated/30 p-3">
              <Metric
                label={t.results.monteCarloP10}
                value={`₺${result.monte_carlo.p10.toLocaleString("tr-TR")}`}
              />
              <Metric
                label={t.results.monteCarloP50}
                value={`₺${result.monte_carlo.p50.toLocaleString("tr-TR")}`}
                highlight
              />
              <Metric
                label={t.results.monteCarloP90}
                value={`₺${result.monte_carlo.p90.toLocaleString("tr-TR")}`}
              />
            </div>
          )}

          {result.co2_reduction_kg > 0 && (
            <p className="text-[11px] text-success">
              🌿 {t.results.co2Reduction}:{" "}
              <span className="font-mono font-semibold">
                {result.co2_reduction_kg.toLocaleString("tr-TR")} kg
              </span>
            </p>
          )}

          {result.reasons.length > 0 && (
            <ul className="space-y-1 text-[11px] text-secondary">
              {result.reasons.map((r, i) => (
                <li key={i}>• {r}</li>
              ))}
            </ul>
          )}

          <p className="text-[10px] text-tertiary">
            {t.results.confidence}: {(result.confidence * 100).toFixed(0)}%
          </p>
        </div>
      )}

      {!result && !mutation.isError && !mutation.isPending && (
        <p className="text-[11px] italic text-tertiary">{t.empty}</p>
      )}
    </div>
  );
}

function NumberInput({
  label,
  value,
  onChange,
  min,
  max,
  step,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <label className="flex flex-col gap-1 text-[10px] uppercase tracking-wider text-secondary">
      {label}
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => onChange(Number(e.target.value))}
        className="rounded-card border border-border bg-surface px-2 py-1 font-mono text-xs text-primary focus:border-accent focus:outline-none"
      />
    </label>
  );
}

function Metric({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="rounded-card border border-border/40 bg-elevated/30 px-2 py-1.5">
      <p className="text-[10px] uppercase tracking-wider text-tertiary">
        {label}
      </p>
      <p
        className={cn(
          "font-mono text-sm font-semibold",
          highlight ? "text-accent" : "text-primary",
        )}
      >
        {value}
      </p>
    </div>
  );
}
