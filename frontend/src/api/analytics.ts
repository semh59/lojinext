import { recordPageViewApiV1AnalyticsPageViewPost } from "../generated/api/analytics/analytics";
import axiosInstance from "../services/api/axios-instance";

/**
 * Faz 3 — sayfa görüntüleme kaydı. Best-effort: hata yutulur, UI'ı bozmaz.
 */
export async function recordPageView(route: string): Promise<void> {
  try {
    await recordPageViewApiV1AnalyticsPageViewPost({ route });
  } catch {
    // analitik best-effort — sessizce geç
  }
}

export interface RouteCount {
  route: string;
  count: number;
}

export interface PageViewStats {
  period_days: number;
  total_views: number;
  top_routes: RouteCount[];
  bottom_routes: RouteCount[];
}

export async function fetchPageViewStats(days = 30): Promise<PageViewStats> {
  const { data } = await axiosInstance.get<PageViewStats>(
    "/admin/analytics/page-views",
    { params: { days } },
  );
  return data;
}
