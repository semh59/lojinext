import { create } from "zustand";
import { persist, createJSONStorage, StateStorage } from "zustand/middleware";
import { withErrorTracking } from "../services/error-middleware";
import { Trip } from "../types";
import { storageService } from "../services/storage-service";
import {
  normalizeTripStatusOrEmpty,
  type TripStatus,
} from "../lib/trip-status";

interface TripFilters {
  durum: TripStatus | "";
  onay_durumu?: "beklemede" | "onaylandi" | "reddedildi" | "";
  search: string;
  baslangic_tarih: string;
  bitis_tarih: string;
  arac_id?: number;
  sofor_id?: number;
  skip?: number;
  limit?: number;
}

interface TripState {
  // Data State
  filters: TripFilters;
  selectedTrip: Trip | null;
  viewMode: "table" | "grid";
  isFormOpen: boolean;
  selectedIds: number[];
  showCharts: boolean;

  // Actions
  setFilters: (filters: Partial<TripFilters>) => void;
  resetFilters: () => void;
  setSelectedTrip: (trip: Trip | null) => void;
  setViewMode: (mode: "table" | "grid") => void;
  toggleForm: (isOpen?: boolean) => void;
  toggleCharts: (show?: boolean) => void;

  // Selection Actions
  toggleSelection: (id: number) => void;
  clearSelection: () => void;
  setSelectedIds: (ids: number[]) => void;

  reset: () => void;
}

const initialFilters: TripFilters = {
  durum: "",
  search: "",
  baslangic_tarih: "",
  bitis_tarih: "",
  skip: 0,
  limit: 100,
};

const userScopedStorage: StateStorage = {
  getItem: (name: string) => {
    const key = storageService.getUserScopedKey(name);
    return localStorage.getItem(key);
  },
  setItem: (name: string, value: string) => {
    const key = storageService.getUserScopedKey(name);
    localStorage.setItem(key, value);
  },
  removeItem: (name: string) => {
    const key = storageService.getUserScopedKey(name);
    localStorage.removeItem(key);
  },
};

export const useTripStore = create<TripState>()(
  persist(
    withErrorTracking((set) => ({
      // Initial State
      filters: initialFilters,
      selectedTrip: null,
      viewMode: "table",
      isFormOpen: false,
      selectedIds: [],
      showCharts: false,

      // Actions
      setFilters: (newFilters) =>
        set((state) => {
          const nextFilters = { ...state.filters, ...newFilters };

          if (Object.prototype.hasOwnProperty.call(newFilters, "durum")) {
            nextFilters.durum = normalizeTripStatusOrEmpty(newFilters.durum);
          }

          return {
            filters: nextFilters,
          };
        }),

      resetFilters: () => set({ filters: initialFilters }),

      setSelectedTrip: (trip) => set({ selectedTrip: trip }),

      setViewMode: (mode) => set({ viewMode: mode }),

      toggleForm: (isOpen) =>
        set((state) => ({
          isFormOpen: isOpen !== undefined ? isOpen : !state.isFormOpen,
          selectedTrip: isOpen === false ? null : state.selectedTrip,
        })),

      toggleSelection: (id) =>
        set((state) => ({
          selectedIds: state.selectedIds.includes(id)
            ? state.selectedIds.filter((i) => i !== id)
            : [...state.selectedIds, id],
        })),

      clearSelection: () => set({ selectedIds: [] }),

      setSelectedIds: (ids) => set({ selectedIds: ids }),

      toggleCharts: (show?: boolean) =>
        set((state) => ({
          showCharts: show !== undefined ? show : !state.showCharts,
        })),

      reset: () =>
        set({
          filters: initialFilters,
          selectedTrip: null,
          isFormOpen: false,
          viewMode: "table",
          selectedIds: [],
          showCharts: false,
        }),
    })),
    {
      name: "lojinext-trip-storage",
      storage: createJSONStorage(() => userScopedStorage),
      merge: (persistedState, currentState) => {
        const persisted = (persistedState as Partial<TripState>) ?? {};
        const persistedFilters = persisted.filters ?? currentState.filters;

        return {
          ...currentState,
          ...persisted,
          filters: {
            ...currentState.filters,
            ...persistedFilters,
            durum: normalizeTripStatusOrEmpty(persistedFilters?.durum),
          },
        };
      },
      partialize: (state) => ({
        filters: state.filters,
        viewMode: state.viewMode,
      }),
    },
  ),
);
