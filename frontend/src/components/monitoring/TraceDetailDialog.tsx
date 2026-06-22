import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Bug, Copy, Loader2, ScrollText, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useLocale } from "../../hooks/useLocale";
import {
  errorService,
  type TraceAuditRow,
  type TraceChainResponse,
  type TraceErrorRow,
} from "@/services/api/error-service";

interface TraceDetailDialogProps {
  traceId: string | null;
  onClose: () => void;
}

const SEVERITY_TONE: Record<string, string> = {
  critical: "bg-danger/10 text-danger border-danger/30",
  error: "bg-orange-500/10 text-orange-500 border-orange-500/30",
  warning: "bg-warning/10 text-warning border-warning/30",
  info: "bg-accent/10 text-accent border-accent/30",
};

function formatTime(iso: string | null | undefined, locale: string) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(locale, {
      day: "2-digit",
      month: "2-digit",
      year: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

function ErrorEventBlock({ evt }: { evt: TraceErrorRow }) {
  const [expanded, setExpanded] = useState(false);
  const locale = useLocale();
  const { t } = useTranslation();
  return (
    <div
      className={`rounded-card border bg-surface px-4 py-3 ${
        SEVERITY_TONE[evt.severity] ?? "border-border"
      }`}
      data-testid="trace-error-block"
    >
      <div className="flex items-center gap-2 mb-1">
        <span
          className={`inline-flex px-1.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider ${
            SEVERITY_TONE[evt.severity] ?? "bg-elevated text-secondary"
          }`}
        >
          {evt.severity}
        </span>
        <span className="text-[10px] font-bold text-tertiary uppercase">
          {evt.layer}
        </span>
        <span className="text-[10px] text-tertiary">{evt.category}</span>
        {evt.count > 1 && (
          <span className="text-[10px] font-bold text-secondary">
            ×{evt.count}
          </span>
        )}
        {evt.resolved_at && (
          <span className="text-[10px] text-success font-semibold ml-auto">
            {t("monitoring.resolved_badge", "✓ Resolved")}
          </span>
        )}
      </div>
      <p className="text-sm font-semibold text-primary leading-snug">
        {evt.message}
      </p>
      {evt.path && (
        <p className="mt-0.5 text-[11px] text-tertiary font-mono truncate">
          {evt.path}
        </p>
      )}
      <div className="mt-1 flex gap-3 text-[10px] text-tertiary">
        <span>
          {t("monitoring.first_seen", "First:")}{" "}
          {formatTime(evt.first_seen, locale)}
        </span>
        <span>
          {t("monitoring.last_seen", "Last:")}{" "}
          {formatTime(evt.last_seen, locale)}
        </span>
      </div>
      {evt.stack_trace && (
        <div className="mt-2">
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="text-[11px] text-accent hover:underline"
          >
            {expanded ? "▾" : "▸"} Stack trace
          </button>
          {expanded && (
            <pre className="mt-1 text-[10px] text-tertiary bg-elevated rounded-card p-2 overflow-x-auto whitespace-pre-wrap">
              {evt.stack_trace}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

function AuditRowBlock({ row }: { row: TraceAuditRow }) {
  const locale = useLocale();
  return (
    <div
      className="rounded-card border border-border bg-surface px-4 py-2"
      data-testid="trace-audit-row"
    >
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-bold text-tertiary uppercase">
          {row.action}
        </span>
        {row.entity && (
          <span className="text-[10px] text-tertiary">
            {row.entity}
            {row.entity_id != null && ` #${row.entity_id}`}
          </span>
        )}
        {row.status && (
          <span
            className={`text-[10px] font-semibold ${
              row.status === "success" ? "text-success" : "text-warning"
            }`}
          >
            {row.status}
          </span>
        )}
        {row.duration_ms != null && (
          <span className="text-[10px] text-tertiary ml-auto">
            {Math.round(row.duration_ms)} ms
          </span>
        )}
      </div>
      <div className="text-[10px] text-tertiary mt-0.5">
        {formatTime(row.created_at, locale)}
        {row.user_id != null && ` · user=${row.user_id}`}
      </div>
    </div>
  );
}

export function TraceDetailDialog({
  traceId,
  onClose,
}: TraceDetailDialogProps) {
  const { t } = useTranslation();
  const { data, isLoading, error } = useQuery<TraceChainResponse>({
    queryKey: ["trace", traceId],
    queryFn: () => errorService.getTraceChain(traceId as string),
    enabled: !!traceId,
    staleTime: 30_000,
  });

  if (!traceId) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
      data-testid="trace-detail-dialog"
    >
      <div
        className="bg-surface rounded-modal border border-border w-[95%] max-w-3xl max-h-[90vh] overflow-hidden flex flex-col shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-elevated">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <Bug className="h-4 w-4 text-accent shrink-0" />
            <h2 className="text-sm font-bold text-primary">
              {t("monitoring.trace_detail", "Trace Details")}
            </h2>
            <code className="text-[11px] font-mono text-tertiary truncate">
              {traceId}
            </code>
            <button
              type="button"
              onClick={() => {
                void navigator.clipboard?.writeText(traceId);
              }}
              className="text-tertiary hover:text-primary"
              title={t("monitoring.trace_copy_title", "Copy Trace ID")}
              data-testid="trace-copy-btn"
            >
              <Copy className="h-3.5 w-3.5" />
            </button>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-tertiary hover:text-primary"
            data-testid="trace-close-btn"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto px-5 py-4 space-y-4">
          {isLoading && (
            <div className="flex items-center justify-center h-32 text-secondary gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm">
                {t("monitoring.trace_loading", "Loading trace chain…")}
              </span>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 rounded-card border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">
              <AlertCircle className="h-4 w-4" />
              {t("monitoring.trace_load_failed", "Could not load trace chain.")}
            </div>
          )}

          {data && !isLoading && (
            <>
              {/* Counts */}
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-card border border-border bg-elevated px-3 py-2">
                  <div className="text-[10px] text-tertiary uppercase font-bold">
                    {t("monitoring.error_records", "Error Records")}
                  </div>
                  <div className="text-lg font-black text-primary">
                    {data.counts.errors}
                  </div>
                </div>
                <div className="rounded-card border border-border bg-elevated px-3 py-2">
                  <div className="text-[10px] text-tertiary uppercase font-bold">
                    {t("monitoring.audit_actions", "Audit Actions")}
                  </div>
                  <div className="text-lg font-black text-primary">
                    {data.counts.audit}
                  </div>
                </div>
              </div>

              {/* Hint */}
              {data.hint &&
                data.counts.errors === 0 &&
                data.counts.audit === 0 && (
                  <div className="rounded-card border border-border bg-elevated px-3 py-2 text-[11px] text-secondary leading-relaxed">
                    <div className="font-bold text-tertiary mb-1 uppercase">
                      {t("monitoring.no_records_found", "No Records Found")}
                    </div>
                    {data.hint}
                  </div>
                )}

              {/* Errors */}
              {data.errors.length > 0 && (
                <section>
                  <h3 className="text-[11px] uppercase font-bold text-tertiary mb-2 flex items-center gap-1">
                    <AlertCircle className="h-3 w-3" />
                    {t(
                      "monitoring.error_records_count",
                      "Error records ({{n}})",
                      {
                        n: data.counts.errors,
                      },
                    )}
                  </h3>
                  <div className="space-y-2">
                    {data.errors.map((e) => (
                      <ErrorEventBlock key={e.id} evt={e} />
                    ))}
                  </div>
                </section>
              )}

              {/* Audit */}
              {data.audit.length > 0 && (
                <section>
                  <h3 className="text-[11px] uppercase font-bold text-tertiary mb-2 flex items-center gap-1">
                    <ScrollText className="h-3 w-3" />
                    {t(
                      "monitoring.audit_actions_count",
                      "Audit actions ({{n}})",
                      {
                        n: data.counts.audit,
                      },
                    )}
                  </h3>
                  <div className="space-y-1.5">
                    {data.audit.map((row) => (
                      <AuditRowBlock key={row.id} row={row} />
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
