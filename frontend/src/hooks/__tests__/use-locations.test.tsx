import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useLocations } from "../use-locations";
import { locationService } from "../../api/locations";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
);

// Mock the service
vi.mock("../../api/locations", () => ({
  locationService: {
    getAll: vi.fn(),
    create: vi.fn(),
    analyze: vi.fn(),
  },
}));

// Mock toast
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe("useLocations hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("useGetLocations should fetch and return locations", async () => {
    const mockData = {
      items: [{ id: 1, cikis_yeri: "A", varis_yeri: "B" }],
      total: 1,
    };
    (locationService.getAll as any).mockResolvedValue(mockData);

    // Render the hook
    const { result } = renderHook(
      () => {
        const hooks = useLocations({ limit: 10, skip: 0 });
        return hooks.useGetLocations();
      },
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
  });

  it("useCreateLocation should call service create", async () => {
    const newLoc = { cikis_yeri: "C", varis_yeri: "D", mesafe_km: 50 };
    (locationService.create as any).mockResolvedValue({ id: 2, ...newLoc });

    const { result } = renderHook(
      () => {
        const hooks = useLocations();
        return hooks.useCreateLocation();
      },
      { wrapper },
    );

    await result.current.mutateAsync(newLoc as any);
    expect(locationService.create).toHaveBeenCalledWith(newLoc);
  });
});
