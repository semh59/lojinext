import { useCallback, useEffect, useRef, useState } from "react";

export type SseStatus = "connecting" | "open" | "error" | "closed";

interface UseEventSourceOptions {
  onMessage?: (data: unknown) => void;
  onError?: (err: Event) => void;
  enabled?: boolean;
  maxReconnectDelay?: number;
}

export function useEventSource(
  url: string,
  options: UseEventSourceOptions = {},
) {
  const {
    onMessage,
    onError,
    enabled = true,
    maxReconnectDelay = 30_000,
  } = options;
  const [status, setStatus] = useState<SseStatus>("closed");
  const isMountedRef = useRef(true);
  const closedByCallerRef = useRef(false);
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelay = useRef(1000);
  const onMessageRef = useRef(onMessage);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);
  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  const connect = useCallback(() => {
    if (!isMountedRef.current || !enabled || !url) return;

    if (isMountedRef.current) setStatus("connecting");
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      if (!isMountedRef.current) {
        es.close();
        return;
      }
      setStatus("open");
      reconnectDelay.current = 1000; // reset on success
    };

    es.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data as string);
        onMessageRef.current?.(parsed);
      } catch {
        if (import.meta.env.DEV) {
          console.debug(
            "[useEventSource] non-JSON message dropped:",
            (event.data as string).slice(0, 100),
          );
        }
      }
    };

    es.onerror = (err) => {
      if (!isMountedRef.current || closedByCallerRef.current) return;
      setStatus("error");
      onErrorRef.current?.(err);
      es.close();
      esRef.current = null;
      // Reconnect with exponential backoff
      const delay = Math.min(reconnectDelay.current, maxReconnectDelay);
      reconnectDelay.current = Math.min(delay * 2, maxReconnectDelay);
      reconnectTimer.current = setTimeout(() => {
        if (isMountedRef.current && !closedByCallerRef.current) connect();
      }, delay);
    };
  }, [url, enabled, maxReconnectDelay]);

  useEffect(() => {
    isMountedRef.current = true;
    closedByCallerRef.current = false;
    if (enabled && url) connect();

    return () => {
      isMountedRef.current = false;
      reconnectDelay.current = 1000; // reset delay when URL changes or unmounts
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      esRef.current?.close();
      esRef.current = null;
    };
  }, [connect, enabled, url]);

  const close = useCallback(() => {
    closedByCallerRef.current = true;
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    esRef.current?.close();
    esRef.current = null;
    setStatus("closed");
  }, []);

  return { status, close };
}
