import { useEffect, useState } from "react";
import {
  Calculator,
  Loader2,
  AlertCircle,
  X,
  CheckCircle2,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useTaskStatus } from "../../hooks/useTaskStatus";
import { tripService } from "../../api/trips";
import { useLocale } from "../../hooks/useLocale";

interface TripCostAnalysisModalProps {
  seferId: number | null;
  onClose: () => void;
}

interface ReconciliationResult {
  fuel_cost?: number;
  driver_share?: number;
  depreciation?: number;
  total_cost?: number;
  [key: string]: unknown;
}

const TRY = (v: number, locale: string) =>
  new Intl.NumberFormat(locale, {
    style: "currency",
    currency: "TRY",
    maximumFractionDigits: 0,
  }).format(v);

export function TripCostAnalysisModal({
  seferId,
  onClose,
}: TripCostAnalysisModalProps) {
  const { t } = useTranslation();
  const [taskId, setTaskId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const task = useTaskStatus(taskId, { intervalMs: 1500 });

  useEffect(() => {
    if (!seferId) return;
    setStartError(null);
    setTaskId(null);
    let cancelled = false;
    tripService
      .startCostAnalysis(seferId)
      .then((res) => {
        if (cancelled) return;
        setTaskId(res.task_id);
      })
      .catch((err) => {
        if (cancelled) return;
        setStartError(
          err?.response?.data?.error?.message ??
            err?.response?.data?.detail ??
            t("trips.cost_start_failed", "Cost analysis could not be started."),
        );
      });
    return () => {
      cancelled = true;
    };
  }, [seferId, t]);

  if (!seferId) return null;

  const result = (task.result ?? {}) as ReconciliationResult;
  const hasNumericResult = [
    "fuel_cost",
    "driver_share",
    "depreciation",
    "total_cost",
  ].some((k) => typeof result[k] === "number");

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
      <div className="relative w-full max-w-xl overflow-hidden rounded-modal border border-border bg-surface shadow-2xl">
        <div className="flex items-center justify-between border-b border-border bg-elevated/40 p-4">
          <div className="flex items-center gap-2">
            <Calculator className="h-5 w-5 text-accent" />
            <h3 className="text-sm font-semibold text-primary">
              {t("trips.cost_modal_title", "Trip #{{id}} — Cost Analysis", {
                id: seferId,
              })}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-1.5 text-secondary transition-colors hover:bg-elevated hover:text-primary"
            aria-label={t("common.close", "Close")}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4 p-6">
          {startError ? (
            <div className="flex items-center gap-2 rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
              <AlertCircle className="h-4 w-4" />
              {startError}
            </div>
          ) : task.status === "IDLE" || task.status === "PROCESSING" ? (
            <div className="flex flex-col items-center gap-3 py-8 text-secondary">
              <Loader2 className="h-8 w-8 animate-spin text-accent" />
              <p className="text-sm">
                {t("trips.cost_running", "Cost analysis is running…")}
              </p>
              <p className="text-[11px] text-tertiary">
                {t(
                  "trips.cost_running_hint",
                  "Calculating fuel + driver share + depreciation.",
                )}
              </p>
            </div>
          ) : task.status === "FAILED" ? (
            <div className="flex items-center gap-2 rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
              <AlertCircle className="h-4 w-4" />
              {task.error ?? t("trips.cost_failed", "Cost analysis failed.")}
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2 rounded-card border border-success/20 bg-success/5 px-4 py-3 text-sm text-success">
                <CheckCircle2 className="h-4 w-4" />
                {t("trips.cost_complete", "Analysis complete.")}
              </div>

              {hasNumericResult ? (
                <div className="grid grid-cols-2 gap-3">
                  <CostRow
                    label={t("trips.cost_fuel", "Fuel Cost")}
                    value={result.fuel_cost}
                    accent="text-warning"
                  />
                  <CostRow
                    label={t("trips.cost_driver", "Driver Share")}
                    value={result.driver_share}
                    accent="text-info"
                  />
                  <CostRow
                    label={t("trips.cost_depreciation", "Depreciation")}
                    value={result.depreciation}
                    accent="text-secondary"
                  />
                  <CostRow
                    label={t("common.total", "Total")}
                    value={result.total_cost}
                    accent="text-accent"
                    emphasis
                  />
                </div>
              ) : (
                <pre className="max-h-64 overflow-auto rounded-card border border-border bg-elevated/30 p-3 font-mono text-[11px] text-secondary">
                  {JSON.stringify(result, null, 2)}
                </pre>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function CostRow({
  label,
  value,
  accent,
  emphasis = false,
}: {
  label: string;
  value: number | undefined;
  accent: string;
  emphasis?: boolean;
}) {
  const locale = useLocale();
  const display = value != null ? TRY(value, locale) : "—";
  return (
    <div
      className={`rounded-card border border-border p-3 ${
        emphasis ? "bg-elevated/60" : "bg-elevated/30"
      }`}
    >
      <p className="text-[10px] font-bold uppercase tracking-widest text-secondary">
        {label}
      </p>
      <p
        className={`mt-1 font-bold ${
          emphasis ? "text-2xl" : "text-lg"
        } ${accent}`}
      >
        {display}
      </p>
    </div>
  );
}
