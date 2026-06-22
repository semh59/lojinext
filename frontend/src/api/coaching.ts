import {
  getCoachingInsightsApiV1CoachingSoforIdInsightsGet,
  sendCoachingApiV1CoachingSoforIdSendPost,
  getCoachingEffectivenessApiV1CoachingEffectivenessGet,
} from "../generated/api/coaching/coaching";

export type CoachingCategory =
  | "yakit_yonetimi"
  | "guzergah_tercihi"
  | "sofor_pratigi"
  | "diger";
export type CoachingPriority = "low" | "medium" | "high";
export type CoachingSource = "llm" | "fallback";

export interface CoachingInsight {
  category: CoachingCategory;
  pattern: string;
  evidence: string[];
  suggestion: string;
  impact_score: number;
}

export interface CoachingInsightsResponse {
  sofor_id: number;
  ad_soyad: string;
  headline: string;
  priority: CoachingPriority;
  insights: CoachingInsight[];
  generated_at: string;
  source: CoachingSource;
}

export interface SendCoachingResponse {
  sent: boolean;
  delivery_id: number | null;
  channel: string;
  sent_at: string;
}

export interface CoachingEffectivenessResponse {
  window_days: number;
  total_sent: number;
  total_evaluated: number;
  improved: number;
  worsened: number;
  improve_rate: number | null;
  avg_score_delta_pct: number | null;
  caveat: string;
}

export const coachingService = {
  /**
   * Şoförün koçluk önerilerini getirir. Backend 30dk Redis cache uygular,
   * frontend de aynı pencereyle TanStack Query cache'i ayarlar.
   */
  getInsights: async (soforId: number): Promise<CoachingInsightsResponse> => {
    const data =
      await getCoachingInsightsApiV1CoachingSoforIdInsightsGet(soforId);
    return data as unknown as CoachingInsightsResponse;
  },

  /**
   * Manuel koçluk mesajını Telegram'a ilet. Backend HTML formatla +
   * html.escape() uygular; XSS koruması sağlanmıştır.
   */
  send: async (
    soforId: number,
    message: string,
    insightCategory?: CoachingCategory,
  ): Promise<SendCoachingResponse> => {
    const data = await sendCoachingApiV1CoachingSoforIdSendPost(soforId, {
      message,
      channel: "telegram",
      insight_category: insightCategory,
    });
    return data as unknown as SendCoachingResponse;
  },

  /**
   * A.5 — Son N günde gönderilmiş koçluk mesajlarının etki özeti.
   * Caveat: skor değişimi yalnız koçluğa atfedilemez.
   */
  getEffectiveness: async (
    days: number = 30,
  ): Promise<CoachingEffectivenessResponse> => {
    const data = await getCoachingEffectivenessApiV1CoachingEffectivenessGet({
      days,
    });
    return data as unknown as CoachingEffectivenessResponse;
  },
};
