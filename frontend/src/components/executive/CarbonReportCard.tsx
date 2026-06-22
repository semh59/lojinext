import { AlertCircle, Leaf, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { useCarbon } from "@/hooks/useExecutive";
import { useExecutiveResources } from "@/resources/useResources";

interface Props {
  className?: string;
}

export function CarbonReportCard({ className }: Props) {
  const { executiveText } = useExecutiveResources();
  const { data, isLoading, error } = useCarbon(30);
  const t = executiveText.carbon;

  if (isLoading) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 rounded-modal border border-border bg-surface p-6 shadow-sm",
          className,
        )}
      >
        <Loader2 className="h-4 w-4 animate-spin text-secondary" />
        <span className="text-sm text-secondary">{t.title}…</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div
        className={cn(
          "flex items-start gap-2 rounded-modal border border-danger/30 bg-danger/5 p-4 text-sm text-danger",
          className,
        )}
      >
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
        {executiveText.errors.loadFailed}
      </div>
    );
  }

  const deltaColor =
    data.delta_pct > 10
      ? "text-danger"
      : data.delta_pct > 0
        ? "text-warning"
        : "text-success";

  const sortedClasses = Object.entries(data.by_euro_class).sort(
    (a, b) => b[1] - a[1],
  );

  return (
    <div
      className={cn(
        "rounded-modal border border-border bg-surface p-6 shadow-sm",
        className,
      )}
    >
      <div className="mb-4 flex items-center gap-2">
        <Leaf className="h-4 w-4 text-success" />
        <div>
          <h3 className="text-xs font-bold uppercase tracking-widest text-secondary">
            {t.title}
          </h3>
          <p className="mt-0.5 text-[10px] text-tertiary">{t.subtitle}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 rounded-card border border-border/40 bg-elevated/30 p-3">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-tertiary">
            {t.totalCo2}
          </p>
          <p className="font-mono text-lg font-bold text-primary">
            {data.total_co2_kg.toLocaleString("tr-TR")}
          </p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-tertiary">
            {t.co2PerKm}
          </p>
          <p className="font-mono text-lg font-bold text-primary">
            {data.co2_per_km.toFixed(2)}
          </p>
        </div>
        <div className="col-span-2">
          <p className="text-[10px] uppercase tracking-wider text-tertiary">
            {t.benchmark}:{" "}
            <span className="font-mono">
              {data.benchmark_co2_per_km.toFixed(2)} kg/km
            </span>
          </p>
          <p className={cn("font-mono text-sm font-semibold", deltaColor)}>
            {data.delta_pct > 0 ? "+" : ""}
            {data.delta_pct.toFixed(1)}%{" "}
            <span className="text-[10px] text-tertiary">
              ({data.delta_pct > 0 ? t.deltaAbove : t.deltaBelow})
            </span>
          </p>
        </div>
      </div>

      {sortedClasses.length > 0 && (
        <div className="mt-3">
          <p className="mb-1.5 text-[10px] uppercase tracking-wider text-secondary">
            {t.byEuroClass}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {sortedClasses.map(([cls, co2]) => (
              <span
                key={cls}
                className="rounded-card border border-border bg-elevated px-2 py-0.5 font-mono text-[10px] text-secondary"
              >
                Euro {cls}: {co2.toLocaleString("tr-TR")} kg
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
