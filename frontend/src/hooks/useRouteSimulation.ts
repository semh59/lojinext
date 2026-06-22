import { useMutation } from "@tanstack/react-query";

import {
  simulateRoute,
  type RouteSimRequest,
  type RouteSimResponse,
} from "../api/route-sim";

/**
 * Faz 10 — Güzergah simülasyonu mutation'ı. Form submit → simulateRoute.
 * Sonuç data'da; loading/error UI'da kullanılır.
 */
export function useRouteSimulation() {
  return useMutation<RouteSimResponse, unknown, RouteSimRequest>({
    mutationFn: simulateRoute,
  });
}
