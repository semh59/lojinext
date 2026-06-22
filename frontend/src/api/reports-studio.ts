import { listTemplatesApiV1ReportsStudioTemplatesGet } from "../generated/api/reports-v2/reports-v2";

export type TemplateId =
  | "ceo_1pager"
  | "fleet_weekly"
  | "fuel_cost_analysis"
  | "vehicle_comparison"
  | "carbon_report"
  | "what_if";

export type TemplateCategory = "executive" | "fleet" | "fuel" | "compliance";

export type TemplateFormat = "pdf" | "excel";

export interface TemplateMeta {
  id: TemplateId;
  title: string;
  description: string;
  category: TemplateCategory;
  formats: TemplateFormat[];
  endpoint_hint: string;
  supports_period: boolean;
  supports_vehicle: boolean;
}

export interface TemplateListResponse {
  templates: TemplateMeta[];
  count: number;
}

export const reportsStudioService = {
  /** RV2.5 — 6 statik şablonun meta listesi. */
  listTemplates: async (): Promise<TemplateListResponse> => {
    const result = await listTemplatesApiV1ReportsStudioTemplatesGet();
    return result as unknown as TemplateListResponse;
  },
};
