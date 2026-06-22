import { Wifi, WifiOff, Loader2, RefreshCw } from "lucide-react";
import type { ConnectionStatus } from "./useMonitoringSocket";

interface Props {
  status: ConnectionStatus;
  notificationCount: number;
  onReconnect: () => void;
}

export function ConnectionStatus({
  status,
  notificationCount,
  onReconnect,
}: Props) {
  const config = {
    connecting: {
      icon: Loader2,
      label: "Bağlanıyor...",
      color: "text-warning",
      spin: true,
      showReconnect: false,
    },
    connected: {
      icon: Wifi,
      label: `Bağlı — ${notificationCount} bildirim`,
      color: "text-success",
      spin: false,
      showReconnect: false,
    },
    disconnected: {
      icon: WifiOff,
      label: "Bağlantı kesildi, yeniden bağlanıyor...",
      color: "text-warning",
      spin: false,
      showReconnect: false,
    },
    error: {
      icon: WifiOff,
      label: "Bağlantı hatası",
      color: "text-danger",
      spin: false,
      showReconnect: true,
    },
    max_retries: {
      icon: WifiOff,
      label: "Bağlantı kurulamadı — maksimum deneme aşıldı",
      color: "text-danger",
      spin: false,
      showReconnect: true,
    },
  }[status];

  const Icon = config.icon;

  return (
    <div
      data-testid="connection-status"
      className="flex items-center justify-between gap-2 rounded-card border border-border bg-surface px-4 py-3"
    >
      <div className="flex items-center gap-2">
        <Icon
          className={`h-4 w-4 ${config.color} ${
            config.spin ? "animate-spin-slow" : ""
          }`}
        />
        <span className={`text-sm font-medium ${config.color}`}>
          {config.label}
        </span>
      </div>
      {config.showReconnect && (
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
