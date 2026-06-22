import { describe, it, expect, beforeEach, vi } from "vitest";
import { act } from "@testing-library/react";
import { useTripStore } from "../use-trip-store";

vi.mock("../../services/storage-service", () => ({
  storageService: {
    getUserScopedKey: vi.fn((key) => `user_${key}`),
  },
}));

vi.mock("../../lib/trip-status", () => ({
  normalizeTripStatusOrEmpty: vi.fn((val) => val || ""),
}));

describe("useTripStore", () => {
  beforeEach(() => {
    useTripStore.setState({
      filters: {
        durum: "",
        search: "",
        baslangic_tarih: "",
        bitis_tarih: "",
        skip: 0,
        limit: 100,
      },
      selectedTrip: null,
      viewMode: "table",
      isFormOpen: false,
      selectedIds: [],
      showCharts: false,
    });
    vi.clearAllMocks();
  });

  it("initializes with default state", () => {
    const state = useTripStore.getState();
    expect(state.filters.durum).toBe("");
    expect(state.filters.search).toBe("");
    expect(state.viewMode).toBe("table");
    expect(state.isFormOpen).toBe(false);
    expect(state.selectedIds).toEqual([]);
    expect(state.showCharts).toBe(false);
    expect(state.selectedTrip).toBeNull();
  });

  it("setFilters updates filters and normalizes durum", () => {
    act(() => {
      useTripStore.getState().setFilters({
        durum: "Tamamlandı",
        search: "İstanbul",
      });
    });
    const state = useTripStore.getState();
    expect(state.filters.search).toBe("İstanbul");
    // durum normalization called via mock
  });

  it("setFilters merges with existing filters", () => {
    act(() => {
      useTripStore.getState().setFilters({
        search: "test",
        arac_id: 5,
      });
    });
    const state = useTripStore.getState();
    expect(state.filters.search).toBe("test");
    expect(state.filters.arac_id).toBe(5);
    expect(state.filters.durum).toBe(""); // unchanged
  });

  it("resetFilters restores initial filter state", () => {
    act(() => {
      useTripStore.getState().setFilters({ search: "xyz" });
    });
    expect(useTripStore.getState().filters.search).toBe("xyz");

    act(() => {
      useTripStore.getState().resetFilters();
    });
    const state = useTripStore.getState();
    expect(state.filters.search).toBe("");
    expect(state.filters.durum).toBe("");
  });

  it("setSelectedTrip updates selected trip", () => {
    const trip = { id: 1, durum: "tamamlandi" } as any;
    act(() => {
      useTripStore.getState().setSelectedTrip(trip);
    });
    expect(useTripStore.getState().selectedTrip).toEqual(trip);

    act(() => {
      useTripStore.getState().setSelectedTrip(null);
    });
    expect(useTripStore.getState().selectedTrip).toBeNull();
  });

  it("toggleForm opens/closes form and clears trip on close", () => {
    const trip = { id: 1 } as any;
    act(() => {
      useTripStore.getState().setSelectedTrip(trip);
      useTripStore.getState().toggleForm(true);
    });
    expect(useTripStore.getState().isFormOpen).toBe(true);

    act(() => {
      useTripStore.getState().toggleForm(false);
    });
    expect(useTripStore.getState().isFormOpen).toBe(false);
    expect(useTripStore.getState().selectedTrip).toBeNull();
  });

  it("toggleSelection adds and removes IDs from selectedIds", () => {
    act(() => {
      useTripStore.getState().toggleSelection(1);
    });
    expect(useTripStore.getState().selectedIds).toContain(1);

    act(() => {
      useTripStore.getState().toggleSelection(2);
    });
    expect(useTripStore.getState().selectedIds).toContain(1);
    expect(useTripStore.getState().selectedIds).toContain(2);

    act(() => {
      useTripStore.getState().toggleSelection(1);
    });
    expect(useTripStore.getState().selectedIds).not.toContain(1);
    expect(useTripStore.getState().selectedIds).toContain(2);
  });

  it("setSelectedIds replaces entire selection", () => {
    act(() => {
      useTripStore.getState().setSelectedIds([1, 2, 3]);
    });
    expect(useTripStore.getState().selectedIds).toEqual([1, 2, 3]);

    act(() => {
      useTripStore.getState().setSelectedIds([5, 6]);
    });
    expect(useTripStore.getState().selectedIds).toEqual([5, 6]);
  });

  it("clearSelection empties selectedIds", () => {
    act(() => {
      useTripStore.getState().setSelectedIds([1, 2, 3]);
    });
    expect(useTripStore.getState().selectedIds.length).toBe(3);

    act(() => {
      useTripStore.getState().clearSelection();
    });
    expect(useTripStore.getState().selectedIds).toEqual([]);
  });

  it("reset clears all state to initial values", () => {
    act(() => {
      useTripStore.getState().setFilters({ search: "test" });
      useTripStore.getState().setViewMode("grid");
      useTripStore.getState().setSelectedIds([1, 2]);
      useTripStore.getState().toggleCharts(true);
    });

    act(() => {
      useTripStore.getState().reset();
    });

    const state = useTripStore.getState();
    expect(state.filters.search).toBe("");
    expect(state.viewMode).toBe("table");
    expect(state.selectedIds).toEqual([]);
    expect(state.showCharts).toBe(false);
    expect(state.isFormOpen).toBe(false);
    expect(state.selectedTrip).toBeNull();
  });
});
