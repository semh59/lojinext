import { useState } from "react";
import { ChevronRight, Download, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { PeriodKey } from "../../resources/tr/reports-studio";
import type { TemplateFormat, TemplateMeta } from "../../api/reports-studio";
import { Button } from "../ui/Button";
import { cn } from "../../lib/utils";
import { useReportsStudioResources } from "../../resources/useResources";
import { getReportTemplateMeta } from "../../lib/status-labels";

interface TemplateConfigPanelProps {
  template: TemplateMeta | null;
  onDownload: (config: TemplateDownloadConfig) => Promise<void>;
}

export interface TemplateDownloadConfig {
  template: TemplateMeta;
  format: TemplateFormat;
  period: PeriodKey;
  vehicleId?: number | null;
}

const PERIOD_KEYS: PeriodKey[] = [
  "current_month",
  "last_month",
  "last_3_months",
  "last_year",
];

export function TemplateConfigPanel({
  template,
  onDownload,
}: TemplateConfigPanelProps) {
  const { reportsStudioText } = useReportsStudioResources();
  const { i18n } = useTranslation();
  const [format, setFormat] = useState<TemplateFormat>("pdf");
  const [period, setPeriod] = useState<PeriodKey>("current_month");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{
    kind: "success" | "error";
    message: string;
  } | null>(null);

  if (!template) {
    return (
      <div
        className="flex h-full min-h-[200px] items-center justify-center rounded-modal border border-dashed border-border bg-elevated/40 p-8 text-center"
        data-testid="config-empty"
      >
        <div className="flex flex-col items-center gap-2 text-secondary">
          <ChevronRight className="h-5 w-5" />
          <span className="text-sm">{reportsStudioText.configHint}</span>
        </div>
      </div>
    );
  }

  const supportedFormats = template.formats;
  const effectiveFormat = supportedFormats.includes(format)
    ? format
    : supportedFormats[0];
  const meta = getReportTemplateMeta(template.id, i18n.language);

  const handleDownload = async () => {
    setBusy(true);
    setFeedback(null);
    try {
      await onDownload({
        template,
        format: effectiveFormat,
        period,
        vehicleId: null,
      });
      setFeedback({
        kind: "success",
        message: reportsStudioText.downloadSuccess,
      });
    } catch (_err) {
      setFeedback({
        kind: "error",
        message: reportsStudioText.downloadError,
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4 rounded-modal border border-border bg-surface p-5 shadow-sm">
      <div>
        <h3 className="text-sm font-semibold text-primary">
          {meta?.title ?? template.title}
        </h3>
        <p className="mt-0.5 text-xs text-secondary">
          {meta?.description ?? template.description}
        </p>
      </div>

      {template.supports_period && (
        <div className="space-y-1">
          <label className="text-xs font-medium text-secondary">
            {reportsStudioText.periodLabel}
          </label>
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value as PeriodKey)}
            className="w-full rounded-card border border-border bg-elevated px-3 py-2 text-sm text-primary focus:border-accent focus:outline-none"
            data-testid="period-select"
          >
            {PERIOD_KEYS.map((p) => (
              <option key={p} value={p}>
                {reportsStudioText.periodOptions[p]}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="space-y-1">
        <label className="text-xs font-medium text-secondary">
          {reportsStudioText.formatLabel}
        </label>
        <div className="flex gap-2">
          {supportedFormats.map((fmt) => (
            <button
              key={fmt}
              type="button"
              onClick={() => setFormat(fmt)}
              className={cn(
                "flex-1 rounded-card border px-3 py-2 text-xs font-semibold uppercase transition-colors",
                effectiveFormat === fmt
                  ? "border-accent bg-accent/10 text-accent"
                  : "border-border bg-elevated text-tertiary hover:text-secondary",
              )}
              data-testid={`format-${fmt}`}
            >
              {fmt}
            </button>
          ))}
        </div>
      </div>

      <Button
        onClick={handleDownload}
        disabled={busy}
        className="w-full justify-center gap-2"
        data-testid="download-button"
      >
        {busy ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            {reportsStudioText.downloading}
          </>
        ) : (
          <>
            <Download className="h-4 w-4" />
            {reportsStudioText.downloadButton}
          </>
        )}
      </Button>

      {feedback && (
        <p
          className={cn(
            "text-center text-xs",
            feedback.kind === "success" ? "text-success" : "text-danger",
          )}
          role="status"
          data-testid={`feedback-${feedback.kind}`}
        >
          {feedback.message}
        </p>
      )}
    </div>
  );
}
