import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  ReactNode,
} from "react";
import { AnimatePresence } from "framer-motion";
import { Toast, ToastType } from "../components/ui/Toast";
import { useAuth } from "./AuthContext";
import { wsService } from "../services/api/ws-service";

interface NotificationToast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
}

export interface LiveNotification {
  id: string;
  baslik: string;
  icerik: string;
  olay_tipi: string;
  olusturma_tarihi: string;
  read: boolean;
}

interface NotificationContextType {
  notify: (type: ToastType, title: string, message?: string) => void;
  lastLiveNotification: LiveNotification | null;
  liveNotifications: LiveNotification[];
  unreadCount: number;
  markAllRead: () => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(
  undefined,
);

const MAX_LIVE_NOTIFICATIONS = 50;

export function NotificationProvider({ children }: { children: ReactNode }) {
  const { user, isLoading: authLoading } = useAuth();
  const [toasts, setToasts] = useState<NotificationToast[]>([]);
  const [liveNotifications, setLiveNotifications] = useState<
    LiveNotification[]
  >([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const notify = useCallback(
    (type: ToastType, title: string, message?: string) => {
      const id = crypto.randomUUID();
      setToasts((prev) => [...prev, { id, type, title, message }]);
      setTimeout(() => removeToast(id), 5000);
    },
    [removeToast],
  );

  const markAllRead = useCallback(() => {
    setUnreadCount(0);
    setLiveNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const lastLiveNotification = liveNotifications[0] ?? null;

  const isAdmin =
    !authLoading && (user?.role === "admin" || user?.role === "super_admin");

  useEffect(() => {
    if (!isAdmin) return;

    let stopped = false;
    // Uncapped, no-delay reconnect used to let a transient backend hiccup
    // (WS handshake rejected right after ticket creation, e.g. admin-check
    // blip or the per-user connection cap) turn into a tight loop that
    // hammered both /ws/ticket and the WS handshake as fast as the event
    // loop allowed. Exponential backoff (capped, reset on a real open)
    // applies to both retry paths below.
    const MAX_RETRY_DELAY_MS = 60_000;
    let retryCount = 0;
    const nextRetryDelay = () => {
      const delay = Math.min(MAX_RETRY_DELAY_MS, 5000 * 2 ** retryCount);
      retryCount += 1;
      return delay;
    };

    const connect = (wsUrl: string) => {
      if (stopped) return;
      if (import.meta.env.DEV)
        console.debug("Connecting to Notification WS...");
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        retryCount = 0;
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === "notification") {
            const payload = message.data;

            const live: LiveNotification = {
              id: payload.id ?? crypto.randomUUID(),
              baslik: payload.baslik,
              icerik: payload.icerik,
              olay_tipi: payload.olay_tipi ?? "",
              olusturma_tarihi:
                payload.olusturma_tarihi ?? new Date().toISOString(),
              read: false,
            };

            setLiveNotifications((prev) =>
              [live, ...prev].slice(0, MAX_LIVE_NOTIFICATIONS),
            );
            setUnreadCount((n) => n + 1);

            let toastType: ToastType = "info";
            if (
              payload.olay_tipi?.includes("DELAY") ||
              payload.olay_tipi?.includes("ERROR")
            ) {
              toastType = "warning";
            } else if (payload.olay_tipi?.includes("ANOMALY")) {
              toastType = "error";
            }
            notify(toastType, payload.baslik, payload.icerik);
          }
        } catch (err) {
          console.error("WS message parse error:", err);
        }
      };

      ws.onclose = () => {
        if (stopped) return;
        const delay = nextRetryDelay();
        if (import.meta.env.DEV)
          console.debug(
            `Notification WS closed. Reconnecting in ${delay}ms...`,
          );
        // Re-fetch a fresh ticket on reconnect to avoid stale/expired ticket.
        setTimeout(() => void init(), delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    const init = async () => {
      if (stopped) return;
      try {
        const ticket = await wsService.getTicket();
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const url = `${protocol}//${window.location.host}/api/v1/admin/ws/live?ticket=${ticket}`;
        connect(url);
      } catch {
        if (!stopped) setTimeout(() => void init(), nextRetryDelay());
      }
    };

    void init();

    return () => {
      stopped = true;
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [isAdmin, notify]);

  return (
    <NotificationContext.Provider
      value={{
        notify,
        lastLiveNotification,
        liveNotifications,
        unreadCount,
        markAllRead,
      }}
    >
      {children}

      <div className="fixed bottom-6 right-6 z-[100] flex w-full max-w-sm flex-col gap-3 pointer-events-none">
        <AnimatePresence mode="popLayout">
          {toasts.map((n) => (
            <Toast key={n.id} {...n} onClose={removeToast} />
          ))}
        </AnimatePresence>
      </div>
    </NotificationContext.Provider>
  );
}

export function useNotify() {
  const context = useContext(NotificationContext);
  if (context === undefined) {
    throw new Error("useNotify must be used within a NotificationProvider");
  }
  return context;
}
