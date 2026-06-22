import axiosInstance from "./axios-instance";

export interface BackendErrorEvent {
  id: number;
  fingerprint: string;
  layer: string;
  category: string;
  severity: string;
  message: string;
  count: number;
  first_seen: string;
  last_seen: string;
  trace_id?: string;
  path?: string;
  metadata: Record<string, unknown>;
  resolved_at?: string;
}

/** @deprecated Use BackendErrorEvent */
export type ErrorEvent = BackendErrorEvent;

export interface ErrorEventsResponse {
  items: BackendErrorEvent[];
  total: number;
  page: number;
  page_size: number;
}

export interface ErrorStatsRow {
  hour: string;
  layer: string;
  severity: string;
  event_count: number;
}

export interface ErrorStatsResponse {
  stats: ErrorStatsRow[];
}

export interface ErrorEventsParams {
  layer?: string;
  severity?: string;
  resolved?: boolean;
  page?: number;
  page_size?: number;
}

// ── Trace chain (GET /system/debug/trace/{id}) ─────────────────────────────

export interface TraceErrorRow {
  id: number;
  layer: string;
  category: string;
  severity: string;
  message: string;
  stack_trace?: string;
  path?: string;
  count: number;
  first_seen: string;
  last_seen: string;
  resolved_at?: string | null;
}

export interface TraceAuditRow {
  id: number;
  action: string;
  entity?: string;
  entity_id?: number;
  user_id?: number;
  new_value?: Record<string, unknown>;
  status?: string;
  duration_ms?: number;
  created_at: string;
}

export interface TraceChainResponse {
  trace_id: string;
  counts: { errors: number; audit: number };
  errors: TraceErrorRow[];
  audit: TraceAuditRow[];
  hint?: string;
}

export const errorService = {
  getEvents: async (
    params: ErrorEventsParams = {},
  ): Promise<ErrorEventsResponse> => {
    const { data } = await axiosInstance.get<ErrorEventsResponse>(
      "/system/error-events",
      {
        params: {
          page: params.page ?? 1,
          page_size: params.page_size ?? 50,
          ...(params.layer ? { layer: params.layer } : {}),
          ...(params.severity ? { severity: params.severity } : {}),
          ...(params.resolved !== undefined
            ? { resolved: params.resolved }
            : {}),
        },
      },
    );
    return data;
  },

  getStats: async (): Promise<ErrorStatsResponse> => {
    const { data } = await axiosInstance.get<ErrorStatsResponse>(
      "/system/error-stats",
    );
    return data;
  },

  resolveEvent: async (eventId: number): Promise<void> => {
    await axiosInstance.post(`/system/error-events/${eventId}/resolve`);
  },

  getTraceChain: async (traceId: string): Promise<TraceChainResponse> => {
    const { data } = await axiosInstance.get<TraceChainResponse>(
      `/system/debug/trace/${encodeURIComponent(traceId)}`,
    );
    return data;
  },

  getSseToken: async (): Promise<string> => {
    const { data } = await axiosInstance.post<{
      token: string;
      expires_in: number;
    }>("/system/error-stream-token");
    const base = import.meta.env.VITE_API_URL || "/api/v1";
    return `${base}/system/error-stream?token=${encodeURIComponent(
      data.token,
    )}`;
  },
};
