import { Wifi, WifiOff, Loader2, RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();

  const config = {
    connecting: {
      icon: Loader2,
      label: t("monitoring.connecting"),
      color: "text-warning",
      spin: true,
      showReconnect: false,
    },
    connected: {
      icon: Wifi,
      label: t("monitoring.connected", { n: notificationCount }),
      color: "text-success",
      spin: false,
      showReconnect: false,
    },
    disconnected: {
      icon: WifiOff,
      label: t("monitoring.disconnected"),
      color: "text-warning",
      spin: false,
      showReconnect: false,
    },
    error: {
      icon: WifiOff,
      label: t("monitoring.error"),
      color: "text-danger",
      spin: false,
      showReconnect: true,
    },
    max_retries: {
      icon: WifiOff,
      label: t("monitoring.max_retries"),
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
          {t("monitoring.reconnect")}
        </button>
      )}
    </div>
  );
}
