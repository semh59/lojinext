import { useQuery } from "@tanstack/react-query";
import { fleetInsightsService, type PeriodType } from "../api/fleet-insights";

export function useFleetComparison(period: PeriodType = "month") {
  return useQuery({
    queryKey: ["reports-v2", "fleet-insights", "comparison", period],
    queryFn: () => fleetInsightsService.getComparison(period),
    staleTime: 10 * 60 * 1000, // 10 dk
    refetchOnWindowFocus: false,
  });
}
