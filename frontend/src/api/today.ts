import { getTodayTriageApiV1ReportsTodayTriageGet } from "../generated/api/reports-v2/reports-v2";

export type TriageCategory =
  | "anomaly"
  | "maintenance"
  | "investigation"
  | "telegram_approval"
  | "active_trip";

export type TriageSeverity = "critical" | "high" | "medium" | "low";

export interface TriageAction {
  label: string;
  url: string;
  action_type: "navigate" | "modal" | "external";
}

export interface TriageItem {
  id: string;
  category: TriageCategory;
  severity: TriageSeverity;
  title: string;
  subtitle: string;
  timestamp: string;
  plaka: string | null;
  actions: TriageAction[];
}

export interface TodayTriageResponse {
  critical_count: number;
  pending_count: number;
  items: TriageItem[];
  active_trips_count: number;
  completed_today_count: number;
  computed_at: string;
}

export const todayService = {
  getTriage: async (): Promise<TodayTriageResponse> => {
    const result = await getTodayTriageApiV1ReportsTodayTriageGet();
    return result as unknown as TodayTriageResponse;
  },
};
