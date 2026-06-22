import { useMutation } from "@tanstack/react-query";
import {
  tripPlannerService,
  type PlanWizardRequestPayload,
  type PlanWizardResponse,
} from "../api/trip-planner";

/**
 * Plan wizard çağrısını mutation olarak yönetir.
 *
 * Mutation kullanma sebebi: kullanıcı butona basana kadar tetiklenmemeli;
 * sonuçlar cache'lenmemeli (her tarih+güzergah kombinasyonu için fresh).
 */
export function usePlanWizard() {
  return useMutation<PlanWizardResponse, Error, PlanWizardRequestPayload>({
    mutationFn: (payload) => tripPlannerService.plan(payload),
  });
}
