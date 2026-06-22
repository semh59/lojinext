import { useQuery } from "@tanstack/react-query";
import { todayService } from "../api/today";

/**
 * Reports v2 RV2.1 — Today/Triage hook.
 * staleTime 1 dk (kritik anomali için kısa, ama sürekli polling değil).
 */
export function useTriage() {
  return useQuery({
    queryKey: ["reports-v2", "today-triage"],
    queryFn: () => todayService.getTriage(),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
    refetchOnWindowFocus: true,
  });
}
