import { useState } from "react";
import { AlertCircle, Download, Loader2, Wrench, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { useNotify } from "@/context/NotificationContext";
import { maintenancePredictionsText } from "@/resources/tr/maintenancePredictions";
import {
  maintenancePredictionsService,
  type MaintenancePrediction,
  type RiskLevel,
} from "@/api/maintenance-predictions";

const RISK_STYLE: Record<RiskLevel, string> = {
  overdue: "bg-danger/10 text-danger border-danger/30",
  soon: "bg-warning/10 text-warning border-warning/30",
  normal: "bg-info/10 text-info border-info/30",
  low: "bg-success/10 text-success border-success/30",
};

interface DrawerProps {
  prediction: MaintenancePrediction | null;
  onClose: () => void;
}

function formatDate(iso: string | null): string {
  if (!iso) return maintenancePredictionsText.table.notApplicable;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${m[3]}.${m[2]}.${m[1]}`;
}

export function MaintenanceDetailDrawer({ prediction, onClose }: DrawerProps) {
  const { notify } = useNotify();
  const [isDownloading, setIsDownloading] = useState(false);

  if (!prediction) return null;

  const handleDownload = async () => {
    // Tahmin için bakım kaydı henüz yok → .ics indirilebilir bir kayıt yok.
    // Kullanıcı bunu çözmek için "tamamlanmamış" gelecek bakım kaydı
    // oluşturmalı; v1'de butonu disabled bırakıyoruz ve mesaj veriyoruz.
    // İleriki sürümde: POST /admin/maintenance → ID al → ICS indir.
    notify(
      "info",
      "Henüz hazır değil",
      "Önce planlanmış bakım kaydı oluşturulmalı.",
    );
    try {
      setIsDownloading(true);
      // Bakım ID'si placeholder: prediction.arac_id (gerçek bakım ID değil)
      // — bu test/UX için ileride POST /admin/maintenance flow eklenmeli.
      await maintenancePredictionsService.downloadIcs(prediction.arac_id);
    } catch (exc: unknown) {
      const err = exc as { response?: { status?: number } };
      if (err?.response?.status === 404) {
        // Beklenen — kayıt yok
        return;
      }
      notify("error", "Hata", maintenancePredictionsText.drawer.downloadError);
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[60] flex items-start justify-end bg-black/40 p-0 backdrop-blur-sm sm:items-center sm:p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="relative flex h-full w-full max-w-md flex-col overflow-hidden border-l border-border bg-surface shadow-2xl sm:h-auto sm:max-h-[90vh] sm:rounded-modal sm:border"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={maintenancePredictionsText.drawer.title}
      >
        <div className="flex items-start justify-between gap-2 border-b border-border bg-elevated/40 p-4">
          <div className="flex items-start gap-2">
            <Wrench className="mt-0.5 h-5 w-5 text-accent" />
            <div>
              <h3 className="text-sm font-semibold text-primary">
                {prediction.plaka}
              </h3>
              <p className="text-[11px] text-secondary">
                {prediction.bakim_tipi}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={maintenancePredictionsText.drawer.close}
            className="rounded-full p-1.5 text-secondary transition-colors hover:bg-elevated hover:text-primary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="custom-scrollbar flex-1 space-y-4 overflow-y-auto p-4">
          {!prediction.predictable ? (
            <div className="flex items-start gap-2 rounded-card border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-warning">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              {maintenancePredictionsText.drawer.notPredictable}
            </div>
          ) : (
            <>
              <section className="space-y-2">
                <h4 className="text-[10px] font-bold uppercase tracking-widest text-secondary">
                  {maintenancePredictionsText.drawer.sections.summary}
                </h4>
                <div className="grid grid-cols-2 gap-2 rounded-card border border-border/40 bg-elevated/30 p-3 text-[11px]">
                  <Field
                    label={
                      maintenancePredictionsText.drawer.labels.predicted_date
                    }
                    value={formatDate(prediction.predicted_date ?? null)}
                  />
                  <Field
                    label={
                      maintenancePredictionsText.drawer.labels.days_remaining
                    }
                    value={
                      prediction.days_remaining != null
                        ? `${prediction.days_remaining} gün`
                        : "—"
                    }
                    accent={prediction.is_overdue ? "danger" : undefined}
                  />
                  <Field
                    label={maintenancePredictionsText.drawer.labels.risk}
                    value={
                      <span
                        className={cn(
                          "inline-block rounded-full border px-1.5 py-0.5 text-[10px] font-bold uppercase",
                          RISK_STYLE[
                            (prediction.risk_level ?? "low") as RiskLevel
                          ],
                        )}
                      >
                        {
                          maintenancePredictionsText.riskLabels[
                            (prediction.risk_level ?? "low") as RiskLevel
                          ]
                        }
                      </span>
                    }
                  />
                  <Field
                    label={maintenancePredictionsText.drawer.labels.confidence}
                    value={`${(prediction.confidence * 100).toFixed(0)}%`}
                  />
                  {(prediction.savings_pct ?? 0) > 0 && (
                    <Field
                      label={maintenancePredictionsText.drawer.labels.savings}
                      value={
                        <span className="font-mono tabular-nums font-semibold text-success">
                          %{(prediction.savings_pct ?? 0).toFixed(1)}
                        </span>
                      }
                    />
                  )}
                </div>
              </section>

              <section className="space-y-2">
                <h4 className="text-[10px] font-bold uppercase tracking-widest text-secondary">
                  {maintenancePredictionsText.drawer.sections.reasons}
                </h4>
                {(prediction.reasons ?? []).length === 0 ? (
                  <p className="text-[11px] italic text-tertiary">—</p>
                ) : (
                  <ul className="space-y-1.5">
                    {(prediction.reasons ?? []).map((r, i) => {
                      const isWarn = r.includes("GECİKMİŞ");
                      return (
                        <li
                          key={i}
                          className={cn(
                            "rounded-card border px-2.5 py-1.5 text-[11px]",
                            isWarn
                              ? "border-danger/30 bg-danger/5 text-danger"
                              : "border-border/40 bg-elevated/30 text-primary",
                          )}
                        >
                          {r}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </section>
            </>
          )}
        </div>

        {prediction.predictable && (
          <div className="border-t border-border bg-elevated/40 p-3">
            <button
              type="button"
              onClick={handleDownload}
              disabled={isDownloading}
              className="inline-flex w-full items-center justify-center gap-2 rounded-card bg-accent px-3 py-2 text-xs font-semibold text-white shadow-sm hover:bg-accent/90 disabled:opacity-50"
            >
              {isDownloading ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Download className="h-3 w-3" />
              )}
              {maintenancePredictionsText.drawer.downloadIcs}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  accent,
}: {
  label: string;
  value: React.ReactNode;
  accent?: "danger";
}) {
  return (
    <div>
      <p className="text-tertiary">{label}</p>
      <p
        className={cn(
          "font-semibold",
          accent === "danger" ? "text-danger" : "text-primary",
        )}
      >
        {value}
      </p>
    </div>
  );
}
