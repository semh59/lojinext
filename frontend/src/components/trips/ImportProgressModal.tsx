import { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  FileSpreadsheet,
  Loader2,
  X,
} from "lucide-react";
import { useTaskStatus } from "../../hooks/useTaskStatus";
import { tripService } from "../../api/trips";

interface ImportProgressModalProps {
  /** null/undefined ise modal kapalı. Dosya verildiğinde async upload başlar. */
  file: File | null;
  onClose: () => void;
  /** Başarı sonrası invalidate vb. tetiklemek için. */
  onComplete?: (summary: ImportSummary) => void;
}

interface ImportSummary {
  success: boolean;
  total_rows: number;
  success_count: number;
  failed_count: number;
  errors: Array<Record<string, unknown> | string>;
}

export function ImportProgressModal({
  file,
  onClose,
  onComplete,
}: ImportProgressModalProps) {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const task = useTaskStatus(taskId, { intervalMs: 1500 });

  useEffect(() => {
    if (!file) {
      setTaskId(null);
      setStartError(null);
      return;
    }
    let cancelled = false;
    setStartError(null);
    setTaskId(null);

    tripService
      .uploadExcelAsync(file)
      .then((res) => {
        if (cancelled) return;
        setTaskId(res.task_id);
      })
      .catch((err) => {
        if (cancelled) return;
        const detail =
          (err?.response?.data?.detail as string | undefined) ??
          "İçe aktarma başlatılamadı.";
        setStartError(detail);
      });

    return () => {
      cancelled = true;
    };
  }, [file]);

  // SUCCESS sonrası dış callback'i bir kez tetikle.
  useEffect(() => {
    if (task.status === "SUCCESS" && task.result && onComplete) {
      onComplete(task.result as ImportSummary);
    }
  }, [task.status]);

  if (!file) return null;

  const summary = (task.result as ImportSummary | undefined) ?? null;
  const errors = Array.isArray(summary?.errors) ? summary!.errors : [];
  const displayErrors = errors.slice(0, 5);

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
      <div className="relative w-full max-w-xl overflow-hidden rounded-modal border border-border bg-surface shadow-2xl">
        <div className="flex items-center justify-between border-b border-border bg-elevated/40 p-4">
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5 text-accent" />
            <div>
              <h3 className="text-sm font-semibold text-primary">
                Excel İçe Aktarma
              </h3>
              <p className="text-[11px] text-secondary truncate max-w-[280px]">
                {file.name}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={task.status === "PROCESSING"}
            className="rounded-full p-1.5 text-secondary transition-colors hover:bg-elevated hover:text-primary disabled:opacity-30"
            aria-label="Kapat"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4 p-5">
          {startError ? (
            <div className="flex items-center gap-2 rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
              <AlertCircle className="h-4 w-4" />
              {startError}
            </div>
          ) : task.status === "IDLE" || task.status === "PROCESSING" ? (
            <div className="flex flex-col items-center gap-3 py-6 text-secondary">
              <Loader2 className="h-8 w-8 animate-spin text-accent" />
              <p className="text-sm font-semibold text-primary">İşleniyor…</p>
              <p className="text-[11px] text-tertiary text-center max-w-sm">
                Excel satırları analiz ediliyor. Büyük dosyalar birkaç dakika
                sürebilir.
              </p>
            </div>
          ) : task.status === "FAILED" ? (
            <div className="flex items-center gap-2 rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
              <AlertCircle className="h-4 w-4" />
              {task.error ?? "İçe aktarma başarısız oldu."}
            </div>
          ) : (
            // SUCCESS
            <>
              <div
                className={`flex items-center gap-2 rounded-card px-4 py-3 text-sm ${
                  (summary?.failed_count ?? 0) > 0
                    ? "border border-warning/30 bg-warning/5 text-warning"
                    : "border border-success/20 bg-success/5 text-success"
                }`}
              >
                {(summary?.failed_count ?? 0) > 0 ? (
                  <AlertCircle className="h-4 w-4" />
                ) : (
                  <CheckCircle2 className="h-4 w-4" />
                )}
                Tamamlandı: {summary?.success_count ?? 0} satır işlendi
                {(summary?.failed_count ?? 0) > 0 &&
                  `, ${summary?.failed_count} satır atlandı`}
                .
              </div>

              <div className="grid grid-cols-3 gap-2 text-center">
                <Stat label="Toplam" value={summary?.total_rows ?? 0} />
                <Stat
                  label="Başarılı"
                  value={summary?.success_count ?? 0}
                  accent="text-success"
                />
                <Stat
                  label="Atlandı"
                  value={summary?.failed_count ?? 0}
                  accent={
                    (summary?.failed_count ?? 0) > 0
                      ? "text-warning"
                      : "text-secondary"
                  }
                />
              </div>

              {displayErrors.length > 0 && (
                <details className="rounded-card border border-border bg-elevated/30 p-3 text-xs">
                  <summary className="cursor-pointer font-semibold text-secondary">
                    İlk {displayErrors.length} hata ({errors.length} toplam)
                  </summary>
                  <ul className="mt-2 space-y-1">
                    {displayErrors.map((err, idx) => (
                      <li
                        key={idx}
                        className="font-mono text-[10px] text-secondary"
                      >
                        {typeof err === "string" ? err : JSON.stringify(err)}
                      </li>
                    ))}
                  </ul>
                </details>
              )}

              <div className="flex justify-end pt-2">
                <button
                  onClick={onClose}
                  className="rounded-card bg-accent px-4 py-2 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-accent/90"
                >
                  Kapat
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  accent = "text-primary",
}: {
  label: string;
  value: number;
  accent?: string;
}) {
  return (
    <div className="rounded-card border border-border bg-elevated/30 p-2">
      <p className="text-[9px] font-bold uppercase tracking-widest text-secondary">
        {label}
      </p>
      <p className={`mt-0.5 text-lg font-bold ${accent}`}>{value}</p>
    </div>
  );
}
