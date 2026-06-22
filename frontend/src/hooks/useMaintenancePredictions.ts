import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  maintenancePredictionsService,
  type MaintenancePrediction,
} from "../api/maintenance-predictions";

/**
 * D.3 — Bakım tahmin listesi React Query hook.
 *
 * Backend zaten 1 saat Redis cache yapıyor; frontend staleTime aynı.
 * Bakım create/complete sonrası invalidate edilir.
 */
export function useMaintenancePredictions() {
  return useQuery<MaintenancePrediction[], Error>({
    queryKey: ["maintenance", "predictions"],
    queryFn: () => maintenancePredictionsService.getAll(),
    staleTime: 60 * 60 * 1000, // 1 saat
    refetchOnWindowFocus: false,
  });
}

/** create/complete mutation'larından sonra çağrılır. */
export function useInvalidatePredictions() {
  const qc = useQueryClient();
  return () =>
    qc.invalidateQueries({ queryKey: ["maintenance", "predictions"] });
}
