import { useCallback, useEffect, useState } from "react";
import { pushService } from "../api/push";

/** Base64url → ArrayBuffer (VAPID applicationServerKey için). */
function urlBase64ToBuffer(base64String: string): ArrayBuffer {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const buf = new ArrayBuffer(raw.length);
  const view = new Uint8Array(buf);
  for (let i = 0; i < raw.length; i += 1) view[i] = raw.charCodeAt(i);
  return buf;
}

export interface PushStatus {
  supported: boolean;
  permission: NotificationPermission | "unsupported";
  subscribed: boolean;
  enabling: boolean;
  error: string | null;
}

const INITIAL: PushStatus = {
  supported: false,
  permission: "unsupported",
  subscribed: false,
  enabling: false,
  error: null,
};

function isSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

/**
 * RV2.PWA Plan §7.3 — push abonelik akışı.
 *
 * - enable(): permission iste → SW ready → public key al → subscribe →
 *   backend'e kaydet
 * - disable(): backend + browser subscription kaldır
 */
export function usePushNotifications() {
  const [status, setStatus] = useState<PushStatus>(INITIAL);

  const refresh = useCallback(async () => {
    if (!isSupported()) {
      setStatus({ ...INITIAL, supported: false });
      return;
    }
    const permission = Notification.permission;
    let subscribed = false;
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      subscribed = sub !== null;
    } catch {
      subscribed = false;
    }
    setStatus((s) => ({
      ...s,
      supported: true,
      permission,
      subscribed,
      error: null,
    }));
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const enable = useCallback(async (): Promise<boolean> => {
    if (!isSupported()) return false;

    setStatus((s) => ({ ...s, enabling: true, error: null }));
    try {
      const perm = await Notification.requestPermission();
      if (perm !== "granted") {
        setStatus((s) => ({
          ...s,
          enabling: false,
          permission: perm,
          error: perm === "denied" ? "Bildirim izni reddedildi." : null,
        }));
        return false;
      }

      const reg = await navigator.serviceWorker.ready;
      const { public_key, push_enabled } =
        await pushService.getVapidPublicKey();
      if (!push_enabled || !public_key) {
        setStatus((s) => ({
          ...s,
          enabling: false,
          error: "Sunucu push desteklemiyor.",
        }));
        return false;
      }

      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToBuffer(public_key),
      });

      const subJson = sub.toJSON() as {
        endpoint?: string;
        keys?: { p256dh?: string; auth?: string };
      };
      if (!subJson.endpoint || !subJson.keys?.p256dh || !subJson.keys?.auth) {
        throw new Error("Subscription geçersiz");
      }

      await pushService.subscribe({
        endpoint: subJson.endpoint,
        keys: {
          p256dh: subJson.keys.p256dh,
          auth: subJson.keys.auth,
        },
        user_agent: navigator.userAgent.slice(0, 200),
      });

      setStatus((s) => ({
        ...s,
        enabling: false,
        permission: "granted",
        subscribed: true,
        error: null,
      }));
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Bilinmeyen hata";
      setStatus((s) => ({ ...s, enabling: false, error: message }));
      return false;
    }
  }, []);

  const disable = useCallback(async (): Promise<boolean> => {
    if (!isSupported()) return false;
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        try {
          await pushService.unsubscribe(sub.endpoint);
        } catch {
          // Backend hatası unsubscribe'ı bloklamaz
        }
        await sub.unsubscribe();
      }
      setStatus((s) => ({ ...s, subscribed: false, error: null }));
      return true;
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Abonelik silinemedi";
      setStatus((s) => ({ ...s, error: message }));
      return false;
    }
  }, []);

  return { ...status, enable, disable, refresh };
}
