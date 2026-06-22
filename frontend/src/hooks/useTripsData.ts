import { useEffect, useMemo, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Ban, Navigation, TrendingUp, Truck } from "lucide-react";

import { tripModuleText, tripStatsText } from "../resources/tr/trips";
import {
  TRIP_STATUS_PLANLANDI,
  TRIP_STATUS_TAMAMLANDI,
  normalizeTripStatus,
  normalizeTripStatusOrEmpty,
} from "../lib/trip-status";
import { tripService } from "../api/trips";
import { useTripStore } from "../stores/use-trip-store";
import { Trip } from "../types";

export function useTripsData() {
  const [searchParams, setSearchParams] = useSearchParams();
  const isInitialSync = useRef(true);

  const { filters, setFilters, showCharts } = useTripStore();

  // Sync URL → store on mount
  useEffect(() => {
    const urlStatus = searchParams.get("durum") || "";
    const urlSearch = searchParams.get("search") || "";
    const urlFrom = searchParams.get("from") || "";
    const urlTo = searchParams.get("to") || "";

    if (urlStatus || urlSearch || urlFrom || urlTo) {
      setFilters({
        durum: normalizeTripStatusOrEmpty(urlStatus),
        search: urlSearch,
        baslangic_tarih: urlFrom,
        bitis_tarih: urlTo,
      });
    }

    isInitialSync.current = false;
  }, [searchParams, setFilters]);

  // Sync store → URL on filter changes
  useEffect(() => {
    if (isInitialSync.current) return;

    const params = new URLSearchParams();
    if (filters.durum) params.set("durum", filters.durum);
    if (filters.search) params.set("search", filters.search);
    if (filters.baslangic_tarih) params.set("from", filters.baslangic_tarih);
    if (filters.bitis_tarih) params.set("to", filters.bitis_tarih);
    setSearchParams(params, { replace: true });
  }, [
    filters.durum,
    filters.search,
    filters.baslangic_tarih,
    filters.bitis_tarih,
    setSearchParams,
  ]);

  const hasActiveFilter = Boolean(
    filters.durum ||
      filters.search ||
      filters.baslangic_tarih ||
      filters.bitis_tarih,
  );

  const {
    data: response,
    isLoading,
    isError,
    error,
    dataUpdatedAt,
  } = useQuery({
    queryKey: ["trips", filters],
    queryFn: () => tripService.getAll(filters),
    staleTime: 5 * 60 * 1000,
    refetchInterval: (query) => {
      const currentData = query.state.data as any;
      if (filters.durum === TRIP_STATUS_PLANLANDI) {
        return 15000;
      }
      if (
        currentData?.items?.some(
          (trip: any) =>
            normalizeTripStatus(trip.durum) === TRIP_STATUS_PLANLANDI,
        )
      ) {
        return 15000;
      }
      return false;
    },
    refetchIntervalInBackground: false,
  });

  const trips: Trip[] = response?.items || [];
  const totalCount: number = response?.meta?.total || 0;

  const tripLoadErrorMessage = useMemo(() => {
    const status = (error as any)?.response?.status;
    return status === 403
      ? tripModuleText.loadErrorForbidden
      : tripModuleText.loadErrorGeneric;
  }, [error]);

  const { data: statsResponse } = useQuery({
    queryKey: [
      "tripStats",
      filters.durum,
      filters.baslangic_tarih,
      filters.bitis_tarih,
    ],
    queryFn: () =>
      tripService.getStats({
        durum: filters.durum,
        baslangic_tarih: filters.baslangic_tarih,
        bitis_tarih: filters.bitis_tarih,
      }),
    staleTime: 5 * 60 * 1000,
  });

  const { data: fuelPerformanceData, isLoading: isFuelPerformanceLoading } =
    useQuery({
      queryKey: ["tripFuelPerformance", filters],
      queryFn: () => tripService.getFuelPerformance(filters),
      enabled: showCharts,
      staleTime: 2 * 60 * 1000,
    });

  const { data: beklemede } = useQuery({
    queryKey: ["trips", "beklemede"],
    queryFn: () => tripService.getBeklemede(),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
  const beklemedeSayisi = beklemede?.length ?? 0;

  // Filtresiz genel stats — materialized view hızını kullanır, ayrı cache key
  const { data: fleetStatsResponse } = useQuery({
    queryKey: ["tripStats", "global"],
    queryFn: () => tripService.getStats({}),
    staleTime: 10 * 60 * 1000,
  });

  const stats = useMemo(() => {
    const src = statsResponse ?? fleetStatsResponse;
    if (!src) return [];

    return [
      {
        label: tripStatsText.totalTripsLabel(
          filters.durum === TRIP_STATUS_TAMAMLANDI,
        ),
        value: src.total_count || 0,
        icon: Truck,
        color: "text-info",
        bg: "bg-info/10",
      },
      {
        label: "Tamamlanan",
        value: src.completed_count || 0,
        icon: Navigation,
        color: "text-success",
        bg: "bg-success/10",
      },
      {
        label: "Toplam Mesafe",
        value: (src.total_distance_km || 0).toLocaleString("tr-TR", {
          maximumFractionDigits: 0,
        }),
        unit: "km",
        icon: TrendingUp,
        color: "text-danger",
        bg: "bg-danger/10",
      },
      {
        label: "Ort. Tüketim",
        value: (src.avg_consumption || 0).toFixed(1),
        unit: "L/100km",
        icon: Truck,
        color: "text-warning",
        bg: "bg-warning/10",
      },
      {
        label: tripStatsText.cancelledLabel,
        value: src.cancelled_count || 0,
        icon: Ban,
        color: "text-secondary",
        bg: "bg-secondary/10",
      },
    ];
  }, [filters.durum, statsResponse, fleetStatsResponse]);

  // Pagination derived values
  const pageSize =
    Number(filters.limit ?? 100) > 0 ? Number(filters.limit ?? 100) : 100;
  const currentSkip = Number(filters.skip ?? 0);
  const currentPage = Math.floor(currentSkip / pageSize) + 1;
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  return {
    // Trip list data
    trips,
    totalCount,
    isLoading,
    isError,
    tripLoadErrorMessage,
    // Stats
    stats,
    // Charts/analytics
    fuelPerformanceData,
    isFuelPerformanceLoading,
    // Filters derived
    hasActiveFilter,
    // Pagination
    pageSize,
    currentSkip,
    currentPage,
    totalPages,
    // Approval queue
    beklemedeSayisi,
    // Last fetch timestamp (ms)
    dataUpdatedAt,
  };
}
