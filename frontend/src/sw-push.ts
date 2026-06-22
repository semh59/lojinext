/// <reference lib="webworker" />
/// <reference types="vite-plugin-pwa/client" />

// Reports v2 RV2.PWA — Service worker with Web Push handler.
//
// Plan §7.3 — `push` ve `notificationclick` event'leri yakalanır. Workbox
// `precacheAndRoute` injectManifest tarafından enjekte edilir.

import { cleanupOutdatedCaches, precacheAndRoute } from "workbox-precaching";

declare const self: ServiceWorkerGlobalScope;

precacheAndRoute(self.__WB_MANIFEST);

// Eski build'lerin precache girdilerini temizle — aksi halde stale app shell
// (eski index.html + eski asset hash'leri) cache'te kalır.
cleanupOutdatedCaches();

// registerType=autoUpdate ile birlikte: yeni SW bekleme durumunda takılmadan
// hemen aktive olsun ve halihazırda açık olan sekmeleri devralsın. Bu olmadan
// kullanıcı sekmeyi tamamen kapatıp açana kadar eski arayüzü görmeye devam eder.
self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event: ExtendableEvent) => {
  event.waitUntil(self.clients.claim());
});

interface PushPayload {
  title?: string;
  body?: string;
  url?: string;
}

self.addEventListener("push", (event: PushEvent) => {
  let data: PushPayload = {};
  try {
    data = (event.data?.json() as PushPayload) ?? {};
  } catch {
    data = { title: "LojiNext", body: event.data?.text() ?? "" };
  }

  const title = data.title ?? "LojiNext";
  const options: NotificationOptions = {
    body: data.body ?? "",
    icon: "/icons/icon-192.png",
    badge: "/icons/badge-72.png",
    data: { url: data.url ?? "/today" },
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

const isSameOrigin = (rawUrl: string): boolean => {
  if (rawUrl.startsWith("/")) return true;
  try {
    return new URL(rawUrl).origin === self.location.origin;
  } catch {
    return false;
  }
};

self.addEventListener("notificationclick", (event: NotificationEvent) => {
  event.notification.close();
  const raw =
    (event.notification.data as { url?: string } | undefined)?.url ?? "/today";
  const url = isSameOrigin(raw) ? raw : "/today";
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((wins) => {
        for (const w of wins) {
          if (
            w.url === new URL(url, self.location.origin).href &&
            "focus" in w
          ) {
            return w.focus();
          }
        }
        if (self.clients.openWindow) {
          return self.clients.openWindow(url);
        }
        return undefined;
      }),
  );
});

// SKIP_WAITING hook (registerType=autoUpdate ile birlikte kullanışlı)
self.addEventListener("message", (event: ExtendableMessageEvent) => {
  if (event.data?.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});
