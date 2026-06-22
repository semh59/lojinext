import { useEffect, useRef, useState, useCallback } from "react";
import { tokenStorage } from "@/services/api/auth-service";

export interface TrainingProgress {
  model_id: string;
  epoch: number;
  total_epochs: number;
  loss: number;
  val_loss?: number;
  status: "running" | "completed" | "failed";
  message?: string;
  accuracy?: number;
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
        const msg = JSON.parse(e.data as string) as {
          type: string;
          data?: TrainingProgress;
          message?: string;
        };
        if (msg.type === "pong") return;
        if (msg.type === "training_progress" && msg.data) {
          setProgress(msg.data);
          setWsStatus(msg.data.status === "running" ? "training" : "idle");
          if (msg.message) {
            setLogs((prev) => [msg.message!, ...prev].slice(0, 200));
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
