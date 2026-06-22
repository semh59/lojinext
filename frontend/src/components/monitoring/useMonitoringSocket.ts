import { useEffect, useRef, useState, useCallback } from "react";
import { tokenStorage } from "@/services/api/auth-service";

export interface WsNotification {
  id: number;
  baslik: string;
  icerik: string;
  olay_tipi: string;
  olusturma_tarihi: string;
}

export type ConnectionStatus =
  | "connecting"
  | "connected"
  | "disconnected"
  | "error"
  | "max_retries";

const MAX_RETRIES = 5;
const BASE_DELAY_MS = 3000;
const PING_INTERVAL_MS = 30_000;

function buildWsUrl(token: string): string {
  const base = (import.meta.env.VITE_API_URL ?? "/api/v1") as string;
  const wsBase = base.startsWith("http")
    ? base.replace(/^http/, "ws")
    : `${window.location.protocol === "https:" ? "wss" : "ws"}://${
        window.location.host
      }${base}`;
  return `${wsBase}/admin/ws/live?token=${token}`;
}

export function useMonitoringSocket() {
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [notifications, setNotifications] = useState<WsNotification[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearPing = () => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
  };

  const connect = useCallback(() => {
    const token = tokenStorage.get();
    if (!token) {
      setStatus("error");
      return;
    }

    const ws = new WebSocket(buildWsUrl(token));
    wsRef.current = ws;
    setStatus("connecting");

    ws.onopen = () => {
      setStatus("connected");
      retryCountRef.current = 0;
      // Keepalive: send ping every 30s to prevent idle disconnect
      pingIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send("ping");
      }, PING_INTERVAL_MS);
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data as string) as {
          type: string;
          data: WsNotification;
        };
        if (msg.type === "notification") {
          setNotifications((prev) => [msg.data, ...prev].slice(0, 100));
        }
        // ignore 'pong' responses
      } catch {
        /* ignore malformed messages */
      }
    };

    ws.onclose = () => {
      clearPing();
      if (retryCountRef.current < MAX_RETRIES) {
        setStatus("disconnected");
        const delay = BASE_DELAY_MS * Math.pow(2, retryCountRef.current);
        retryCountRef.current += 1;
        retryTimerRef.current = setTimeout(connect, delay);
      } else {
        setStatus("max_retries");
      }
    };

    ws.onerror = () => {
      clearPing();
      setStatus("error");
    };
  }, []);

  const reconnect = useCallback(() => {
    retryCountRef.current = 0;
    if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
    wsRef.current?.close();
    connect();
  }, [connect]);

  useEffect(() => {
    connect();
    return () => {
      clearPing();
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const clearNotifications = useCallback(() => setNotifications([]), []);

  return { status, notifications, clearNotifications, reconnect };
}
