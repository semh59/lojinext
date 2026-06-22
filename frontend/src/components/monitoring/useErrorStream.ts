import { useEffect, useRef, useState } from "react";
import {
  errorService,
  type BackendErrorEvent,
} from "@/services/api/error-service";

export type SseStatus = "idle" | "connecting" | "connected" | "error";

export function useErrorStream(enabled: boolean) {
  const [liveEvents, setLiveEvents] = useState<BackendErrorEvent[]>([]);
  const [sseStatus, setSseStatus] = useState<SseStatus>("idle");
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setSseStatus("connecting");

    errorService
      .getSseToken()
      .then((url) => {
        if (cancelled) return;
        const es = new EventSource(url);
        esRef.current = es;

        es.onopen = () => {
          if (!cancelled) setSseStatus("connected");
        };
        es.onmessage = (e) => {
          if (cancelled) return;
          try {
            const evt = JSON.parse(e.data as string) as BackendErrorEvent;
            if (evt && evt.id) {
              setLiveEvents((prev) => [evt, ...prev].slice(0, 50));
            }
          } catch {
            /* ignore malformed */
          }
        };
        es.onerror = () => {
          if (!cancelled) setSseStatus("error");
          es.close();
        };
      })
      .catch(() => {
        if (!cancelled) setSseStatus("error");
      });

    return () => {
      cancelled = true;
      esRef.current?.close();
      esRef.current = null;
    };
  }, [enabled]);

  return { liveEvents, sseStatus };
}
