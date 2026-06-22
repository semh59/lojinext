import { useState } from "react";
import { Sparkles } from "lucide-react";

import { CrossFeatureSavings } from "@/components/executive/CrossFeatureSavings";
import { FleetEfficiencyCard } from "@/components/executive/FleetEfficiencyCard";
import { PeriodComparisonCard } from "@/components/fleet-insights/PeriodComparisonCard";
import { cn } from "@/lib/utils";
import { usePageTitle } from "@/hooks/usePageTitle";
import type { PeriodType } from "@/api/fleet-insights";

const PERIODS: Array<{ id: PeriodType; label: string }> = [
  { id: "week", label: "Bu Hafta" },
  { id: "month", label: "Bu Ay" },
];

export default function FleetInsightsPage() {
  usePageTitle("Filo İçgörü");
  const [period, setPeriod] = useState<PeriodType>("month");

  return (
    <div className="space-y-6 p-6">
      <header className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <Sparkles className="mt-1 h-6 w-6 text-accent" />
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-primary">
              Filo İçgörü
            </h1>
            <p className="mt-1 text-sm text-secondary">
              FVI + period-over-period + cross-feature etki
            </p>
          </div>
        </div>
        {/* Period switcher */}
        <div className="flex gap-1 rounded-xl border border-border bg-surface p-1">
          {PERIODS.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setPeriod(p.id)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-xs font-semibold transition-all",
                period === p.id
                  ? "bg-accent text-white shadow-sm"
                  : "text-secondary hover:text-primary",
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-12">
        <FleetEfficiencyCard className="md:col-span-4" />
        <PeriodComparisonCard period={period} className="md:col-span-8" />
        <CrossFeatureSavings className="md:col-span-12" />
      </div>
    </div>
  );
}
