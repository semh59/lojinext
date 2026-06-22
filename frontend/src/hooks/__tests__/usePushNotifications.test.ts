import { describe, expect, it, vi, beforeEach } from "vitest";
import { act } from "@testing-library/react";
import { renderHook, waitFor } from "../../test/test-utils";

vi.mock("../../api/push", () => ({
  pushService: {
    getVapidPublicKey: vi.fn(),
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
  },
}));

import { pushService } from "../../api/push";
import { usePushNotifications } from "../usePushNotifications";

// jsdom Notification + serviceWorker + PushManager stub'ları
function setupBrowserMocks(opts: {
  permission?: NotificationPermission;
  requestResult?: NotificationPermission;
  existingSubscription?: PushSubscription | null;
  subscribeResult?: PushSubscription;
}) {
  const requestPermission = vi
    .fn()
    .mockResolvedValue(opts.requestResult ?? "granted");
  const getSubscription = vi
    .fn()
    .mockResolvedValue(opts.existingSubscription ?? null);
  const subscribe = vi.fn().mockResolvedValue(opts.subscribeResult ?? null);

  Object.defineProperty(global, "Notification", {
    configurable: true,
    value: { permission: opts.permission ?? "default", requestPermission },
  });

  Object.defineProperty(global, "PushManager", {
    configurable: true,
    value: class {},
  });

  Object.defineProperty(global.navigator, "serviceWorker", {
    configurable: true,
    value: {
      ready: Promise.resolve({
        pushManager: { getSubscription, subscribe },
      }),
    },
  });

  Object.defineProperty(global.navigator, "userAgent", {
    configurable: true,
    value: "TestUA",
  });

  return { requestPermission, getSubscription, subscribe };
}

const fakeSubscription = {
  endpoint: "https://push.example/abc",
  toJSON: () => ({
    endpoint: "https://push.example/abc",
    keys: { p256dh: "p256dh-key", auth: "auth-key" },
  }),
  unsubscribe: vi.fn().mockResolvedValue(true),
} as unknown as PushSubscription;

describe("usePushNotifications — RV2.PWA", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("happy path: enable() permission grant + subscribe + backend kayıt", async () => {
    const browser = setupBrowserMocks({
      permission: "default",
      requestResult: "granted",
      subscribeResult: fakeSubscription,
    });

    (
      pushService.getVapidPublicKey as ReturnType<typeof vi.fn>
    ).mockResolvedValue({ public_key: "BPUB_BASE64_URL", push_enabled: true });
    (pushService.subscribe as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 1,
      endpoint: "https://push.example/abc",
      created_at: new Date().toISOString(),
      last_used_at: null,
    });

    const { result } = renderHook(() => usePushNotifications());
    await waitFor(() => expect(result.current.supported).toBe(true));

    let ok = false;
    await act(async () => {
      ok = await result.current.enable();
    });

    expect(ok).toBe(true);
    expect(browser.requestPermission).toHaveBeenCalled();
    expect(browser.subscribe).toHaveBeenCalledWith(
      expect.objectContaining({ userVisibleOnly: true }),
    );
    expect(pushService.subscribe).toHaveBeenCalledWith({
      endpoint: "https://push.example/abc",
      keys: { p256dh: "p256dh-key", auth: "auth-key" },
      user_agent: "TestUA",
    });
    expect(result.current.subscribed).toBe(true);
    expect(result.current.permission).toBe("granted");
  });

  it("permission denied → enable() false döner, error mesajı set edilir", async () => {
    setupBrowserMocks({ permission: "default", requestResult: "denied" });

    const { result } = renderHook(() => usePushNotifications());
    await waitFor(() => expect(result.current.supported).toBe(true));

    let ok = true;
    await act(async () => {
      ok = await result.current.enable();
    });

    expect(ok).toBe(false);
    expect(result.current.subscribed).toBe(false);
    expect(result.current.permission).toBe("denied");
    expect(result.current.error).toContain("reddedildi");
    // Backend çağrılmadı
    expect(pushService.subscribe).not.toHaveBeenCalled();
  });

  it("push_enabled false → enable() false döner, abone olunmaz", async () => {
    setupBrowserMocks({
      permission: "default",
      requestResult: "granted",
      subscribeResult: fakeSubscription,
    });
    (
      pushService.getVapidPublicKey as ReturnType<typeof vi.fn>
    ).mockResolvedValue({ public_key: "", push_enabled: false });

    const { result } = renderHook(() => usePushNotifications());
    await waitFor(() => expect(result.current.supported).toBe(true));

    let ok = true;
    await act(async () => {
      ok = await result.current.enable();
    });

    expect(ok).toBe(false);
    expect(result.current.error).toContain("Sunucu push desteklemiyor");
    expect(pushService.subscribe).not.toHaveBeenCalled();
  });

  it("disable: backend unsubscribe + browser unsubscribe çağrılır", async () => {
    setupBrowserMocks({
      permission: "granted",
      existingSubscription: fakeSubscription,
    });
    (pushService.unsubscribe as ReturnType<typeof vi.fn>).mockResolvedValue(
      undefined,
    );

    const { result } = renderHook(() => usePushNotifications());
    await waitFor(() => expect(result.current.subscribed).toBe(true));

    let ok = false;
    await act(async () => {
      ok = await result.current.disable();
    });

    expect(ok).toBe(true);
    expect(pushService.unsubscribe).toHaveBeenCalledWith(
      "https://push.example/abc",
    );
    expect(fakeSubscription.unsubscribe).toHaveBeenCalled();
    expect(result.current.subscribed).toBe(false);
  });
});
