import {
  getPatternsApiV1AdminInvestigationsPatternsGet,
  listInvestigationsApiV1AdminInvestigationsGet,
  createInvestigationApiV1AdminInvestigationsPost,
  getInvestigationApiV1AdminInvestigationsInvIdGet,
  updateInvestigationApiV1AdminInvestigationsInvIdPatch,
  softDeleteInvestigationApiV1AdminInvestigationsInvIdDelete,
  reclassifyInvestigationApiV1AdminInvestigationsInvIdClassifyPost,
} from "../generated/api/investigations/investigations";

export type SuspicionLevel = "low" | "medium" | "high" | "unknown";
export type InvestigationStatus =
  | "open"
  | "assigned"
  | "investigating"
  | "resolved"
  | "closed";
export type ResolutionType =
  | "real_theft"
  | "false_alarm"
  | "data_error"
  | "inconclusive";

export interface Investigation {
  id: number;
  anomaly_id: number;
  status: InvestigationStatus;
  suspicion_score: number | null;
  suspicion_level: SuspicionLevel | null;
  assigned_to_user_id: number | null;
  notes: string | null;
  resolution_type: ResolutionType | null;
  evidence_files: string[];
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  plaka: string | null;
  sofor_adi: string | null;
  sapma_yuzde: number | null;
}

export interface PatternMatch {
  sofor_id: number | null;
  sofor_adi: string | null;
  arac_id: number | null;
  plaka: string | null;
  occurrence_count: number;
  avg_suspicion_score: number;
  last_seen: string;
}

export interface InvestigationUpdatePayload {
  status?: InvestigationStatus;
  assigned_to_user_id?: number;
  notes?: string;
  resolution_type?: ResolutionType;
  evidence_files?: string[];
}

export const investigationService = {
  list: async (
    params: {
      status?: InvestigationStatus;
      suspicion_level?: SuspicionLevel;
      days?: number;
      limit?: number;
    } = {},
  ): Promise<Investigation[]> => {
    const data = await listInvestigationsApiV1AdminInvestigationsGet(
      params as unknown as Parameters<
        typeof listInvestigationsApiV1AdminInvestigationsGet
      >[0],
    );
    return data as unknown as Investigation[];
  },

  get: async (id: number): Promise<Investigation> => {
    const data = await getInvestigationApiV1AdminInvestigationsInvIdGet(id);
    return data as unknown as Investigation;
  },

  create: async (
    anomalyId: number,
    initialNotes?: string,
  ): Promise<Investigation> => {
    const data = await createInvestigationApiV1AdminInvestigationsPost({
      anomaly_id: anomalyId,
      initial_notes: initialNotes ?? null,
    });
    return data as unknown as Investigation;
  },

  update: async (
    id: number,
    payload: InvestigationUpdatePayload,
  ): Promise<Investigation> => {
    const data = await updateInvestigationApiV1AdminInvestigationsInvIdPatch(
      id,
      payload as unknown as Parameters<
        typeof updateInvestigationApiV1AdminInvestigationsInvIdPatch
      >[1],
    );
    return data as unknown as Investigation;
  },

  close: async (id: number): Promise<void> => {
    await softDeleteInvestigationApiV1AdminInvestigationsInvIdDelete(id);
  },

  classify: async (id: number) => {
    const data =
      await reclassifyInvestigationApiV1AdminInvestigationsInvIdClassifyPost(
        id,
      );
    return data;
  },

  getPatterns: async (
    params: { days?: number; min_count?: number; limit?: number } = {},
  ): Promise<PatternMatch[]> => {
    const data = await getPatternsApiV1AdminInvestigationsPatternsGet(
      params as unknown as Parameters<
        typeof getPatternsApiV1AdminInvestigationsPatternsGet
      >[0],
    );
    return data as unknown as PatternMatch[];
  },
};
