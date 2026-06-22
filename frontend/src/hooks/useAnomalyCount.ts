import { useQuery } from "@tanstack/react-query";
import { anomalyService } from "../api/anomalies";

/**
 * Belirli bir tip + dönem için anomali toplamı. Aynı queryKey'i
 * FuelAnomalyWidget ile paylaşır → TanStack Query cache tek istekle yeter.
 */
export function useAnomalyCount(
  tip: "tuketim" | "maliyet" | "sefer",
  days = 30,
): { count: number; isLoaded: boolean } {
  const { data } = useQuery({
    queryKey: ["fuelAnomalyWidget", tip, days],
    queryFn: () => anomalyService.getRecentAnomalies({ tip, days, limit: 5 }),
    staleTime: 5 * 60 * 1000,
  });
  return { count: data?.total ?? 0, isLoaded: data !== undefined };
}
