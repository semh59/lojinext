import { useEffect, useRef, useState, useCallback } from "react";
import { tokenStorage } from "@/services/api/auth-service";

// Wire shape from training_ws_manager.broadcast() (app/core/services/ml_service.py
// update_progress) — flat, not nested under a "data" key. See EgitimKuyrugu's
// durum check constraint (app/database/models.py) for the full state set;
// ilerleme is a 0.0-100.0 float, not an epoch counter (no epoch/loss/accuracy
// data exists on this feed at all).
export interface TrainingProgress {
  task_id: number;
  arac_id: number;
  ilerleme: number;
  durum: "WAITING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELED";
  error: boolean;
  detail?: string | null;
}

export type TrainingWsStatus =
  | "connecting"
  | "idle"
  | "training"
  | "error"
  | "disconnected";

function buildWsUrl(token: string): string {
  const base = (import.meta.env.VITE_API_URL ?? "/api/v1") as string;
  const wsBase = base.startsWith("http")
    ? base.replace(/^http/, "ws")
    : `${window.location.protocol === "https:" ? "wss" : "ws"}://${
        window.location.host
      }${base}`;
  return `${wsBase}/admin/ws/training?token=${token}`;
}

export function useTrainingSocket() {
  const [wsStatus, setWsStatus] = useState<TrainingWsStatus>("connecting");
  const [progress, setProgress] = useState<TrainingProgress | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const connect = useCallback(() => {
    const token = tokenStorage.get();
    if (!token) {
      setWsStatus("error");
      return;
    }

    const ws = new WebSocket(buildWsUrl(token));
    wsRef.current = ws;
    setWsStatus("connecting");

    ws.onopen = () => {
      setWsStatus("idle");
      pingRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send("ping");
      }, 30_000);
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data as string) as
          | { type: "pong" }
          | ({ type: "progress" } & TrainingProgress);
        if (msg.type === "pong") return;
        if (msg.type === "progress") {
          setProgress(msg);
          setWsStatus(msg.durum === "RUNNING" ? "training" : "idle");
          if (msg.error && msg.detail) {
            setLogs((prev) => [msg.detail!, ...prev].slice(0, 200));
          }
        }
      } catch {
        /* ignore */
      }
    };

    ws.onclose = () => {
      if (pingRef.current) clearInterval(pingRef.current);
      setWsStatus("disconnected");
    };

    ws.onerror = () => {
      if (pingRef.current) clearInterval(pingRef.current);
      setWsStatus("error");
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (pingRef.current) clearInterval(pingRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { wsStatus, progress, logs, reconnect: connect };
}
