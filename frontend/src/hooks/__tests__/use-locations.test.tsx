/**
 * 0-mock epiği Faz 2: gerçek backend'e karşı gerçek React Query hook testi
 * (bkz services/api/__tests__/location-service.test.ts'in başındaki desen
 * açıklaması). locationService artık mock'lu değil — sadece toast (UI
 * side-effect, dış sınır değil) dokümante mock'lu kalıyor.
 */
import { describe, it, expect, vi, beforeAll, afterAll } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../test/real-backend";

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("useLocations hooks (real backend)", () => {
  let useLocations: typeof import("../use-locations").useLocations;
  let locationService: typeof import("../../api/locations").locationService;
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  const runTag = Date.now();
  let createdId: number | undefined;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ useLocations } = await import("../use-locations"));
    ({ locationService } = await import("../../api/locations"));
  });

  afterAll(async () => {
    if (createdId) {
      await locationService.delete(createdId).catch(() => undefined);
      await locationService.delete(createdId).catch(() => undefined);
    }
    vi.unstubAllEnvs();
  });

  it("useGetLocations should fetch real, filtered locations", async () => {
    // Seed a real, uniquely-tagged row so the filtered search below has a
    // deterministic result regardless of whatever else is in the shared
    // test DB.
    const seeded = await locationService.create({
      cikis_yeri: `HookTestA${runTag}`,
      varis_yeri: `HookTestB${runTag}`,
      mesafe_km: 42,
    } as any);
    createdId = (seeded as any).id;

    const { result } = renderHook(
      () => {
        const hooks = useLocations({ search: `hooktesta${runTag}` });
        return hooks.useGetLocations();
      },
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
    expect((result.current.data?.items[0] as any).id).toBe(createdId);
  });

  it("useCreateLocation should really persist via the service", async () => {
    const newLoc = {
      cikis_yeri: `HookTestC${runTag}`,
      varis_yeri: `HookTestD${runTag}`,
      mesafe_km: 50,
    };

    const { result } = renderHook(
      () => {
        const hooks = useLocations();
        return hooks.useCreateLocation();
      },
      { wrapper },
    );

    const created = await result.current.mutateAsync(newLoc as any);
    expect((created as any).id).toBeGreaterThan(0);

    // Real round-trip: really persisted, fetchable by id.
    const fetched = await locationService.getById((created as any).id);
    expect((fetched as any).id).toBe((created as any).id);

    await locationService.delete((created as any).id).catch(() => undefined);
    await locationService.delete((created as any).id).catch(() => undefined);
  });
});
