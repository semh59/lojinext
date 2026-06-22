import { AlertCircle, Loader2 } from "lucide-react";

import { RouteHeatmap } from "@/features/route-lab/RouteHeatmap";
import { RouteProfileChart } from "@/features/route-lab/RouteProfileChart";
import { RouteSimForm } from "@/features/route-lab/RouteSimForm";
import { RouteSimSummary } from "@/features/route-lab/RouteSimSummary";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useRouteSimulation } from "@/hooks/useRouteSimulation";
import { routeLabText } from "@/resources/tr/routeLab";

function errorMessage(err: unknown): string {
  const status =
    typeof err === "object" && err !== null
      ? (err as { response?: { status?: number } }).response?.status
      : undefined;
  if (status === 429) return routeLabText.errors.rateLimited;
  if (status === 502) return routeLabText.errors.providerDown;
  return routeLabText.errors.generic;
}

export default function RouteLabPage() {
  usePageTitle(routeLabText.heading);
  const sim = useRouteSimulation();

  return (
    <div className="flex flex-col gap-6 p-4 sm:p-6">
      <div>
        <h1 className="text-xl font-semibold text-primary">
          {routeLabText.heading}
        </h1>
        <p className="text-sm text-secondary">{routeLabText.description}</p>
      </div>

      <RouteSimForm
        onSubmit={(req) => sim.mutate(req)}
        submitting={sim.isPending}
      />

      {sim.isPending && (
        <div className="flex items-center justify-center gap-2 py-10 text-secondary">
          <Loader2 className="h-5 w-5 animate-spin" />
          {routeLabText.form.submitting}
        </div>
      )}

      {sim.isError && (
        <div className="flex items-center gap-2 rounded-modal border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-500">
          <AlertCircle className="h-4 w-4" />
          {errorMessage(sim.error)}
        </div>
      )}

      {!sim.isPending && !sim.data && !sim.isError && (
        <div className="flex items-center justify-center py-10 text-sm text-secondary">
          {routeLabText.empty}
        </div>
      )}

      {sim.data && (
        <div className="flex flex-col gap-4">
          {sim.data.elevation_coverage_pct < 100 && (
            <div className="rounded-modal border border-amber-500/40 bg-amber-500/10 px-4 py-2 text-xs text-amber-600">
              {routeLabText.coverageWarning}
            </div>
          )}
          <RouteSimSummary result={sim.data} />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <RouteProfileChart segments={sim.data.segments} />
            <RouteHeatmap segments={sim.data.segments} />
          </div>
        </div>
      )}
    </div>
  );
}
