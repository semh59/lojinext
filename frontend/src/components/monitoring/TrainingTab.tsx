import {
  RefreshCw,
  Brain,
  CheckCircle,
  XCircle,
  Wifi,
  WifiOff,
  Loader2,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { useTrainingSocket, type TrainingWsStatus } from "./useTrainingSocket";

function WsStatusBar({
  status,
  onReconnect,
}: {
  status: TrainingWsStatus;
  onReconnect: () => void;
}) {
  const config: Record<
    TrainingWsStatus,
    {
      icon: typeof Wifi;
      label: string;
      color: string;
      spin: boolean;
      reconnect: boolean;
    }
  > = {
    connecting: {
      icon: Loader2,
      label: "Bağlanıyor...",
      color: "text-warning",
      spin: true,
      reconnect: false,
    },
    idle: {
      icon: Wifi,
      label: "Bağlı — Bekleniyor",
      color: "text-success",
      spin: false,
      reconnect: false,
    },
    training: {
      icon: Wifi,
      label: "Bağlı — Eğitim devam ediyor",
      color: "text-accent",
      spin: false,
      reconnect: false,
    },
    disconnected: {
      icon: WifiOff,
      label: "Bağlantı kesildi",
      color: "text-warning",
      spin: false,
      reconnect: true,
    },
    error: {
      icon: WifiOff,
      label: "Bağlantı hatası",
      color: "text-danger",
      spin: false,
      reconnect: true,
    },
  };
  const { icon: Icon, label, color, spin, reconnect } = config[status];

  return (
    <div className="flex items-center justify-between rounded-card border border-border bg-surface px-4 py-3">
      <div className="flex items-center gap-2">
        <Icon
          className={`h-4 w-4 ${color} ${spin ? "animate-spin-slow" : ""}`}
        />
        <span className={`text-sm font-medium ${color}`}>{label}</span>
      </div>
      {reconnect && (
        <button
          onClick={onReconnect}
          className="flex items-center gap-1.5 text-xs font-semibold text-secondary hover:text-primary transition-colors"
        >
          <RefreshCw size={13} />
          Tekrar Bağlan
        </button>
      )}
    </div>
  );
}

export function TrainingTab() {
  const { wsStatus, progress, logs, reconnect } = useTrainingSocket();

  const pct = progress
    ? Math.round((progress.epoch / progress.total_epochs) * 100)
    : 0;

  return (
    <div className="space-y-4">
      <WsStatusBar status={wsStatus} onReconnect={reconnect} />

      {/* No active training */}
      {!progress && (wsStatus === "idle" || wsStatus === "connecting") && (
        <div className="flex h-48 flex-col items-center justify-center gap-3 rounded-modal border border-dashed border-border text-secondary">
          <Brain size={32} strokeWidth={1.25} className="text-tertiary" />
          <div className="text-center">
            <p className="text-sm font-medium">Aktif eğitim yok</p>
            <p className="text-xs text-tertiary mt-0.5">
              Model eğitimi başladığında burada görünecek
            </p>
          </div>
        </div>
      )}

      {/* Active training progress */}
      {progress && (
        <Card padding="lg" className="space-y-4">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-primary">
                  Model Eğitimi
                </h3>
                {progress.status === "running" && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent/10 text-accent text-[10px] font-black">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                    DEVAM EDİYOR
                  </span>
                )}
                {progress.status === "completed" && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-success/10 text-success text-[10px] font-black">
                    <CheckCircle size={10} />
                    TAMAMLANDI
                  </span>
                )}
                {progress.status === "failed" && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-danger/10 text-danger text-[10px] font-black">
                    <XCircle size={10} />
                    BAŞARISIZ
                  </span>
                )}
              </div>
              <p className="text-xs text-tertiary mt-0.5 font-mono">
                {progress.model_id}
              </p>
            </div>
            <span className="text-2xl font-black text-primary">{pct}%</span>
          </div>

          {/* Progress bar */}
          <div className="space-y-1">
            <div className="h-2 rounded-full bg-elevated overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  progress.status === "failed"
                    ? "bg-danger"
                    : progress.status === "completed"
                      ? "bg-success"
                      : "bg-accent"
                }`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <p className="text-[11px] text-tertiary">
              Epoch {progress.epoch} / {progress.total_epochs}
            </p>
          </div>

          {/* Metrics */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-card bg-elevated px-3 py-2">
              <p className="text-[10px] font-bold uppercase tracking-wider text-tertiary">
                Loss
              </p>
              <p className="text-lg font-black text-primary">
                {progress.loss.toFixed(4)}
              </p>
            </div>
            {progress.val_loss != null && (
              <div className="rounded-card bg-elevated px-3 py-2">
                <p className="text-[10px] font-bold uppercase tracking-wider text-tertiary">
                  Val Loss
                </p>
                <p className="text-lg font-black text-primary">
                  {progress.val_loss.toFixed(4)}
                </p>
              </div>
            )}
            {progress.accuracy != null && (
              <div className="rounded-card bg-elevated px-3 py-2">
                <p className="text-[10px] font-bold uppercase tracking-wider text-tertiary">
                  Accuracy
                </p>
                <p className="text-lg font-black text-primary">
                  {(progress.accuracy * 100).toFixed(1)}%
                </p>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Log feed */}
      {logs.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-secondary uppercase tracking-wider">
              Eğitim Günlüğü
            </h3>
            <span className="text-[10px] text-tertiary">
              {logs.length} kayıt
            </span>
          </div>
          <div className="max-h-64 overflow-y-auto rounded-card border border-border bg-elevated p-3 space-y-1 font-mono">
            {logs.map((log, i) => (
              <p key={i} className="text-[11px] text-secondary leading-relaxed">
                {log}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
