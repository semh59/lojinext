import { useMutation, useQuery } from "@tanstack/react-query";
import {
  executiveService,
  type WhatIfRequest,
  type WhatIfResponse,
} from "../api/executive";

const STALE_30M = 30 * 60 * 1000;

export function useFvi() {
  return useQuery({
    queryKey: ["executive", "fvi"],
    queryFn: () => executiveService.getFvi(),
    staleTime: STALE_30M,
    refetchOnWindowFocus: false,
  });
}

export function useCarbon(days = 30) {
  return useQuery({
    queryKey: ["executive", "carbon", days],
    queryFn: () => executiveService.getCarbon(days),
    staleTime: STALE_30M,
    refetchOnWindowFocus: false,
  });
}

export function useCompliance(daysHorizon = 90) {
  return useQuery({
    queryKey: ["executive", "compliance", daysHorizon],
    queryFn: () => executiveService.getCompliance(daysHorizon),
    staleTime: STALE_30M,
    refetchOnWindowFocus: false,
  });
}

export function useCashflow(days = 90) {
  return useQuery({
    queryKey: ["executive", "cashflow", days],
    queryFn: () => executiveService.getCashflow(days),
    staleTime: STALE_30M,
    refetchOnWindowFocus: false,
  });
}

export function useCrossFeature(days = 90) {
  return useQuery({
    queryKey: ["executive", "cross-feature", days],
    queryFn: () => executiveService.getCrossFeature(days),
    staleTime: STALE_30M,
    refetchOnWindowFocus: false,
  });
}

export function useBusFactor(n = 3) {
  return useQuery({
    queryKey: ["executive", "bus-factor", n],
    queryFn: () => executiveService.getBusFactor(n),
    staleTime: STALE_30M,
    refetchOnWindowFocus: false,
  });
}

export function useWhatIf() {
  return useMutation<WhatIfResponse, Error, WhatIfRequest>({
    mutationFn: (payload) => executiveService.runWhatIf(payload),
  });
}
