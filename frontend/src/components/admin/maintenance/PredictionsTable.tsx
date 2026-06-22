import { useMemo, useState } from "react";
import { AlertCircle, Info, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { useMaintenancePredictions } from "@/hooks/useMaintenancePredictions";
import { maintenancePredictionsText } from "@/resources/tr/maintenancePredictions";
import type {
  MaintenancePrediction,
  RiskLevel,
} from "@/api/maintenance-predictions";
import { MaintenanceDetailDrawer } from "./MaintenanceDetailDrawer";

const RISK_ORDER: Record<RiskLevel, number> = {
  overdue: 0,
  soon: 1,
  normal: 2,
  low: 3,
};

const RISK_BADGE: Record<RiskLevel, string> = {
  overdue: "bg-danger/10 text-danger border-danger/30",
  soon: "bg-warning/10 text-warning border-warning/30",
  normal: "bg-info/10 text-info border-info/30",
  low: "bg-success/10 text-success border-success/30",
};

function formatDate(iso: string | null): string {
  if (!iso) return maintenancePredictionsText.table.notApplicable;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${m[3]}.${m[2]}.${m[1]}`;
}

export function PredictionsTable() {
  const { data = [], isLoading, error } = useMaintenancePredictions();
  const [selected, setSelected] = useState<MaintenancePrediction | null>(null);

  const sorted = useMemo(() => {
    // Önce predictable=true, sonra risk_level sıralı (overdue → low),
    // sonra predicted_date'e göre. Predictable=false en altta.
    return [...data].sort((a, b) => {
      if (a.predictable !== b.predictable) return a.predictable ? -1 : 1;
      if (!a.predictable) return 0;
      const ra =
        RISK_ORDER[(a.risk_level ?? "low") as RiskLevel] -
        RISK_ORDER[(b.risk_level ?? "low") as RiskLevel];
      if (ra !== 0) return ra;
      return (a.predicted_date ?? "").localeCompare(b.predicted_date ?? "");
    });
  }, [data]);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-12 text-secondary">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="text-sm">Yükleniyor…</span>
      </div>
    );
  }

  if (error) {
    const status = (error as { response?: { status?: number } })?.response
      ?.status;
    const msg =
      status === 503
        ? maintenancePredictionsText.errors.flagOff
        : status === 403
          ? maintenancePredictionsText.errors.forbidden
          : maintenancePredictionsText.errors.loadFailed;
    return (
      <div className="flex items-center gap-2 rounded-card border border-danger/30 bg-danger/5 px-3 py-3 text-sm text-danger">
        <AlertCircle className="h-4 w-4 shrink-0" />
        {msg}
      </div>
    );
  }

  if (sorted.length === 0) {
    return (
      <div className="flex items-center gap-2 rounded-card border border-border bg-elevated/30 px-3 py-3 text-sm text-secondary">
        <Info className="h-4 w-4" />
        {maintenancePredictionsText.table.empty}
      </div>
    );
  }

  const cols = maintenancePredictionsText.table.columns;

  return (
    <>
      <div className="overflow-x-auto rounded-modal border border-border bg-surface shadow-sm">
        <table className="w-full text-xs">
          <thead className="bg-elevated/40">
            <tr>
              <th className="px-3 py-2 text-left font-bold uppercase tracking-wider text-secondary">
                {cols.plaka}
              </th>
              <th className="px-3 py-2 text-left font-bold uppercase tracking-wider text-secondary">
                {cols.bakim_tipi}
              </th>
              <th className="px-3 py-2 text-right font-bold uppercase tracking-wider text-secondary">
                {cols.predicted_date}
              </th>
              <th className="px-3 py-2 text-right font-bold uppercase tracking-wider text-secondary">
                {cols.days_remaining}
              </th>
              <th className="px-3 py-2 text-center font-bold uppercase tracking-wider text-secondary">
                {cols.risk_level}
              </th>
              <th className="px-3 py-2 text-right font-bold uppercase tracking-wider text-secondary">
                {cols.confidence}
              </th>
              <th className="px-3 py-2 text-right font-bold uppercase tracking-wider text-secondary">
                {cols.savings}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {sorted.map((p) => (
              <tr
                key={`${p.arac_id}:${p.bakim_tipi}`}
                onClick={() => setSelected(p)}
                className={cn(
                  "cursor-pointer hover:bg-elevated/30",
                  !p.predictable && "opacity-60",
                )}
              >
                <td className="px-3 py-2 font-mono font-bold text-primary">
                  {p.plaka}
                </td>
                <td className="px-3 py-2 text-secondary">{p.bakim_tipi}</td>
                <td className="px-3 py-2 text-right font-mono tabular-nums text-primary">
                  {p.predictable ? (
                    formatDate(p.predicted_date ?? null)
                  ) : (
                    <span className="italic text-tertiary">
                      {maintenancePredictionsText.table.unpredictable}
                    </span>
                  )}
                </td>
                <td
                  className={cn(
                    "px-3 py-2 text-right font-mono tabular-nums",
                    p.is_overdue ? "text-danger font-semibold" : "text-primary",
                  )}
                >
                  {p.days_remaining != null
                    ? `${p.days_remaining > 0 ? "+" : ""}${p.days_remaining}`
                    : maintenancePredictionsText.table.notApplicable}
                </td>
                <td className="px-3 py-2 text-center">
                  {p.predictable && (
                    <span
                      className={cn(
                        "inline-block rounded-full border px-1.5 py-0.5 text-[10px] font-bold uppercase",
                        RISK_BADGE[(p.risk_level ?? "low") as RiskLevel],
                      )}
                    >
                      {
                        maintenancePredictionsText.riskLabels[
                          (p.risk_level ?? "low") as RiskLevel
                        ]
                      }
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 text-right font-mono tabular-nums text-secondary">
                  {p.predictable
                    ? `${((p.confidence ?? 0) * 100).toFixed(0)}%`
                    : "—"}
                </td>
                <td className="px-3 py-2 text-right font-mono tabular-nums">
                  {(p.savings_pct ?? 0) > 0 ? (
                    <span className="font-semibold text-success">
                      %{(p.savings_pct ?? 0).toFixed(1)}
                    </span>
                  ) : (
                    <span className="text-tertiary">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <MaintenanceDetailDrawer
        prediction={selected}
        onClose={() => setSelected(null)}
      />
    </>
  );
}
