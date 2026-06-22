import { useState } from "react";
import { AlertCircle, Loader2 } from "lucide-react";

import { TemplateGallery } from "../components/reports-studio/TemplateGallery";
import {
  TemplateConfigPanel,
  type TemplateDownloadConfig,
} from "../components/reports-studio/TemplateConfigPanel";
import { useReportTemplates } from "../hooks/useReportsStudio";
import type { PeriodKey } from "../resources/tr/reports-studio";
import { useReportsStudioResources } from "../resources/useResources";
import type { TemplateMeta } from "../api/reports-studio";
import { reportsApi, executiveApi } from "../services/api";
import { usePageTitle } from "../hooks/usePageTitle";

function periodToDates(period: PeriodKey): {
  start_date?: string;
  end_date?: string;
  months?: number;
} {
  const today = new Date();
  const isoDate = (d: Date) => d.toISOString().slice(0, 10);
  switch (period) {
    case "current_month": {
      const start = new Date(today.getFullYear(), today.getMonth(), 1);
      return { start_date: isoDate(start), end_date: isoDate(today) };
    }
    case "last_month": {
      const start = new Date(today.getFullYear(), today.getMonth() - 1, 1);
      const end = new Date(today.getFullYear(), today.getMonth(), 0);
      return { start_date: isoDate(start), end_date: isoDate(end) };
    }
    case "last_3_months": {
      const start = new Date(today.getFullYear(), today.getMonth() - 3, 1);
      return {
        start_date: isoDate(start),
        end_date: isoDate(today),
        months: 3,
      };
    }
    case "last_year":
    default: {
      const start = new Date(today.getFullYear() - 1, today.getMonth(), 1);
      return {
        start_date: isoDate(start),
        end_date: isoDate(today),
        months: 12,
      };
    }
  }
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  window.URL.revokeObjectURL(url);
}

async function dispatchDownload(config: TemplateDownloadConfig): Promise<void> {
  const { template, format, period } = config;
  const dateStr = new Date().toISOString().slice(0, 10);
  const params = periodToDates(period);

  if (template.id === "ceo_1pager") {
    await executiveApi.downloadPdf();
    return;
  }

  if (template.id === "fleet_weekly") {
    if (format === "pdf") {
      const blob = await reportsApi.downloadPdf(
        "fleet_summary",
        undefined,
        params as Record<string, string | number>,
      );
      triggerBlobDownload(blob, `filo-haftalik-${dateStr}.pdf`);
    } else {
      const blob = await reportsApi.downloadExcel(
        "fleet_summary",
        params as Record<string, string | number>,
      );
      triggerBlobDownload(blob, `filo-haftalik-${dateStr}.xlsx`);
    }
    return;
  }

  if (template.id === "fuel_cost_analysis") {
    if (format === "pdf") {
      const blob = await reportsApi.downloadPdf(
        "fleet_summary",
        undefined,
        params as Record<string, string | number>,
      );
      triggerBlobDownload(blob, `yakit-maliyet-${dateStr}.pdf`);
    } else {
      const blob = await reportsApi.downloadExcel(
        "cost_trend",
        params as Record<string, string | number>,
      );
      triggerBlobDownload(blob, `yakit-maliyet-${dateStr}.xlsx`);
    }
    return;
  }

  if (template.id === "vehicle_comparison") {
    if (format === "pdf") {
      const blob = await reportsApi.downloadPdf(
        "vehicle_detail",
        undefined,
        params as Record<string, string | number>,
      );
      triggerBlobDownload(blob, `arac-karsilastirma-${dateStr}.pdf`);
    } else {
      const blob = await reportsApi.downloadExcel(
        "vehicle_report",
        params as Record<string, string | number>,
      );
      triggerBlobDownload(blob, `arac-karsilastirma-${dateStr}.xlsx`);
    }
    return;
  }

  if (template.id === "carbon_report") {
    // Karbon raporu için PDF/Excel henüz hazır değil — fleet_summary üzerinden
    // yedek olarak indirilir (E.3 metric'leri PDF'e v2.1'de dahil edilecek).
    if (format === "excel") {
      const blob = await reportsApi.downloadExcel(
        "cost_trend",
        params as Record<string, string | number>,
      );
      triggerBlobDownload(blob, `karbon-raporu-${dateStr}.xlsx`);
      return;
    }
    const blob = await reportsApi.downloadPdf(
      "fleet_summary",
      undefined,
      params as Record<string, string | number>,
    );
    triggerBlobDownload(blob, `karbon-raporu-${dateStr}.pdf`);
    return;
  }

  if (template.id === "what_if") {
    // What-if PDF aktif senaryoyu Strategic Cockpit üzerinden indiriyor
    await executiveApi.downloadPdf();
    return;
  }
}

export default function ReportsStudioPage() {
  const { reportsStudioText } = useReportsStudioResources();
  usePageTitle(reportsStudioText.heading);

  const { data, isLoading, isError } = useReportTemplates();
  const [selected, setSelected] = useState<TemplateMeta | null>(null);

  const templates = data?.templates ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold text-primary">
          {reportsStudioText.heading}
        </h1>
        <p className="text-sm text-secondary">
          {reportsStudioText.description}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-tertiary">
            {reportsStudioText.galleryTitle}
          </h2>
          {isLoading && (
            <div
              className="flex h-48 items-center justify-center rounded-modal border border-border bg-elevated/40"
              data-testid="gallery-loading"
            >
              <Loader2 className="h-5 w-5 animate-spin text-secondary" />
            </div>
          )}
          {isError && (
            <div
              className="flex h-48 items-center justify-center gap-2 rounded-modal border border-danger/40 bg-danger/5 text-sm text-danger"
              data-testid="gallery-error"
            >
              <AlertCircle className="h-4 w-4" />
              {reportsStudioText.galleryError}
            </div>
          )}
          {!isLoading && !isError && templates.length === 0 && (
            <p className="rounded-modal border border-dashed border-border p-8 text-center text-sm text-secondary">
              {reportsStudioText.galleryEmpty}
            </p>
          )}
          {!isLoading && !isError && templates.length > 0 && (
            <TemplateGallery
              templates={templates}
              selectedId={selected?.id ?? null}
              onSelect={(t) => setSelected(t)}
            />
          )}
        </div>
        <div className="lg:col-span-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-tertiary">
            {reportsStudioText.configTitle}
          </h2>
          <TemplateConfigPanel
            template={selected}
            onDownload={dispatchDownload}
          />
        </div>
      </div>
    </div>
  );
}
