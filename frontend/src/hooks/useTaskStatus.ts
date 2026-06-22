import { useQuery } from "@tanstack/react-query";
import { tripService } from "../api/trips";

type TaskStatus = "PROCESSING" | "SUCCESS" | "FAILED" | "IDLE";

interface UseTaskStatusOptions {
  /** Polling aralığı (ms). Default 2000ms — backend hafif yük altında. */
  intervalMs?: number;
}

/**
 * Background job polling hook. `taskId` null/undefined ise sorgu durur (IDLE).
 * SUCCESS veya FAILED'a ulaşıldığında polling otomatik durur.
 */
export function useTaskStatus(
  taskId: string | null | undefined,
  options: UseTaskStatusOptions = {},
) {
  const { intervalMs = 2000 } = options;

  const query = useQuery({
    queryKey: ["task-status", taskId],
    queryFn: () => tripService.getTaskStatus(taskId!),
    enabled: !!taskId,
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      if (status === "SUCCESS" || status === "FAILED") return false;
      return intervalMs;
    },
    staleTime: 0,
  });

  const status: TaskStatus = !taskId
    ? "IDLE"
    : (query.data?.status as TaskStatus | undefined) ?? "PROCESSING";

  return {
    ...query,
    status,
    result: query.data?.result,
    error: query.data?.error,
    isTerminal: status === "SUCCESS" || status === "FAILED",
  };
}
