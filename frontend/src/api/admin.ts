// Thin facade over orval-generated admin API functions.
// Preserves the same named exports and service object shapes as the original
// frontend/src/services/api/admin-service.ts so callers need no changes.

import { getAllConfigsApiV1AdminConfigGet } from "../generated/api/admin-config/admin-config";
import { getConfigApiV1AdminConfigKeyGet } from "../generated/api/admin-config/admin-config";
import { updateConfigApiV1AdminConfigKeyPut } from "../generated/api/admin-config/admin-config";

import { listUsersApiV1AdminUsersGet } from "../generated/api/admin-users/admin-users";
import { createUserApiV1AdminUsersPost } from "../generated/api/admin-users/admin-users";
import { updateUserApiV1AdminUsersUserIdPut } from "../generated/api/admin-users/admin-users";
import { deleteUserApiV1AdminUsersUserIdDelete } from "../generated/api/admin-users/admin-users";

import { getRolesApiV1AdminRolesGet } from "../generated/api/admin-roles/admin-roles";
import { createRoleApiV1AdminRolesPost } from "../generated/api/admin-roles/admin-roles";
import { updateRoleApiV1AdminRolesRoleIdPut } from "../generated/api/admin-roles/admin-roles";
import { deleteRoleApiV1AdminRolesRoleIdDelete } from "../generated/api/admin-roles/admin-roles";

import { triggerTrainingApiV1AdminMlTrainAracIdPost } from "../generated/api/admin-ml/admin-ml";
import { getTrainingQueueApiV1AdminMlQueueGet } from "../generated/api/admin-ml/admin-ml";
import { getModelVersionsApiV1AdminMlVersionsAracIdGet } from "../generated/api/admin-ml/admin-ml";

import { createMaintenanceApiV1AdminMaintenancePost } from "../generated/api/admin-maintenance/admin-maintenance";
import { getUpcomingAlertsApiV1AdminMaintenanceAlertsGet } from "../generated/api/admin-maintenance/admin-maintenance";
import { markCompleteApiV1AdminMaintenanceBakimIdCompletePatch } from "../generated/api/admin-maintenance/admin-maintenance";
import { getVehicleHistoryApiV1AdminMaintenanceAracIdGet } from "../generated/api/admin-maintenance/admin-maintenance";

import { getAdminHealthApiV1AdminHealthGet } from "../generated/api/admin-health/admin-health";
import { resetCircuitBreakerApiV1AdminHealthCircuitBreakerResetPost } from "../generated/api/admin-health/admin-health";
import { triggerManualBackupApiV1AdminHealthBackupTriggerPost } from "../generated/api/admin-health/admin-health";

import { listRulesApiV1AdminNotificationsRulesGet } from "../generated/api/admin-notifications/admin-notifications";
import { createRuleApiV1AdminNotificationsRulesPost } from "../generated/api/admin-notifications/admin-notifications";

import { getFuelAccuracyApiV1AdminFuelAccuracyGet } from "../generated/api/admin-fuel-accuracy/admin-fuel-accuracy";

import {
  importHistoryApiV1AdminImportsHistoryGet,
  rollbackImportApiV1AdminImportsJobIdRollbackPost,
} from "../generated/api/admin-imports/admin-imports";
import axiosInstance from "../services/api/axios-instance";

// ── Type definitions ──────────────────────────────────────────────────────────

export interface AdminConfigItem {
  anahtar: string;
  deger: unknown;
  tip: string;
  birim?: string;
  min_deger?: number;
  max_deger?: number;
  grup: string;
  aciklama?: string;
  yeniden_baslat: boolean;
}

export interface AdminUserRecord {
  id: number;
  email?: string | null;
  ad_soyad: string;
  aktif: boolean;
  rol_id?: number | null;
  son_giris?: string | null;
  rol?: {
    id?: number;
    ad?: string;
    yetkiler?: Record<string, boolean>;
  } | null;
}

export interface AdminUserCreateData {
  email: string;
  ad_soyad: string;
  sifre: string;
  rol_id: number;
  aktif?: boolean;
}

export interface AdminUserUpdateData {
  email?: string;
  ad_soyad?: string;
  sifre?: string;
  rol_id?: number;
  aktif?: boolean;
}

export interface AdminRoleRecord {
  id: number;
  ad: string;
  yetkiler: Record<string, boolean>;
}

export interface AdminRoleCreateData {
  ad: string;
  yetkiler: Record<string, boolean>;
}

export interface AdminTrainingQueueItem {
  id: number;
  arac_id?: number;
  durum?: string;
  metrics?: {
    algorithm?: string;
    rmse?: number;
  } | null;
  training_time_seconds?: number | null;
  error_message?: string | null;
  trigger_reason?: string | null;
  created_at: string;
}

export type BakimTipi = "PERIYODIK" | "ARIZA" | "ACIL";

export interface AdminMaintenanceCreateData {
  arac_id: number;
  bakim_tipi: BakimTipi;
  km_bilgisi: number;
  bakim_tarihi: string;
  maliyet: number;
  detaylar: string;
}

export interface FuelAccuracyArac {
  arac_id: number;
  plaka?: string | null;
  sample_size: number;
  mape_pct?: number | null;
}

export interface FuelAccuracyStats {
  period_days: number;
  sample_size: number;
  mape_pct?: number | null;
  rmse_l_100km?: number | null;
  mean_predicted?: number | null;
  mean_actual?: number | null;
  bias_pct?: number | null;
  coverage_pct: number;
  breakdown_by_arac: FuelAccuracyArac[];
}

export interface AttributionOverridePayload {
  sefer_id: number;
  new_arac_id?: number | null;
  new_sofor_id?: number | null;
  reason: string;
}

// ── Known permissions ─────────────────────────────────────────────────────────

export const KNOWN_PERMISSIONS: { group: string; keys: string[] }[] = [
  {
    group: "Sefer",
    keys: ["sefer:read", "sefer:write", "sefer:onayla"],
  },
  { group: "Yakıt & Şoför", keys: ["yakit:write", "sofor:write"] },
  {
    group: "Anomali & Kalibrasyon",
    keys: ["anomali:yonet", "kalibrasyon_goruntule"],
  },
  {
    group: "Kullanıcı & Rol",
    keys: [
      "kullanici_goruntule",
      "kullanici_ekle",
      "kullanici_duzenle",
      "kullanici_sil",
      "rol_oku",
      "rol_yaz",
    ],
  },
  {
    group: "Bakım & Atama",
    keys: ["bakim_oku", "bakim_ekle", "attribution_duzenle"],
  },
  {
    group: "Sistem",
    keys: [
      "konfig_goruntule",
      "konfig_duzenle",
      "model_goruntule",
      "import_goruntule",
      "notification_rule_goruntule",
      "sistem_saglik_goruntule",
    ],
  },
];

// ── Individual API objects (flat exports, backward-compat) ────────────────────

export const adminApi = {
  getConfigs: async (group?: string): Promise<AdminConfigItem[]> => {
    const params = group ? { group } : undefined;
    return getAllConfigsApiV1AdminConfigGet(
      params,
    ) as unknown as AdminConfigItem[];
  },

  getConfig: async (key: string): Promise<AdminConfigItem> => {
    return getConfigApiV1AdminConfigKeyGet(key) as unknown as AdminConfigItem;
  },

  updateConfig: async (key: string, value: unknown, reason?: string) => {
    return updateConfigApiV1AdminConfigKeyPut(key, {
      value,
      reason,
    } as unknown as Parameters<typeof updateConfigApiV1AdminConfigKeyPut>[1]);
  },
};

export const adminUsersApi = {
  getAll: async (skip = 0, limit = 100): Promise<AdminUserRecord[]> => {
    return listUsersApiV1AdminUsersGet({
      skip,
      limit,
    }) as unknown as AdminUserRecord[];
  },

  create: async (body: AdminUserCreateData): Promise<AdminUserRecord> => {
    return createUserApiV1AdminUsersPost(
      body as unknown as Parameters<typeof createUserApiV1AdminUsersPost>[0],
    ) as unknown as AdminUserRecord;
  },

  update: async (
    id: number,
    body: AdminUserUpdateData,
  ): Promise<AdminUserRecord> => {
    return updateUserApiV1AdminUsersUserIdPut(
      id,
      body as unknown as Parameters<
        typeof updateUserApiV1AdminUsersUserIdPut
      >[1],
    ) as unknown as AdminUserRecord;
  },

  delete: async (id: number): Promise<void> => {
    await deleteUserApiV1AdminUsersUserIdDelete(id);
  },
};

export const adminRolesApi = {
  getAll: async (): Promise<AdminRoleRecord[]> => {
    return getRolesApiV1AdminRolesGet() as unknown as AdminRoleRecord[];
  },

  create: async (body: AdminRoleCreateData): Promise<AdminRoleRecord> => {
    return createRoleApiV1AdminRolesPost(
      body as unknown as Parameters<typeof createRoleApiV1AdminRolesPost>[0],
    ) as unknown as AdminRoleRecord;
  },

  update: async (
    roleId: number,
    body: AdminRoleCreateData,
  ): Promise<AdminRoleRecord> => {
    return updateRoleApiV1AdminRolesRoleIdPut(
      roleId,
      body as unknown as Parameters<
        typeof updateRoleApiV1AdminRolesRoleIdPut
      >[1],
    ) as unknown as AdminRoleRecord;
  },

  remove: async (roleId: number): Promise<void> => {
    await deleteRoleApiV1AdminRolesRoleIdDelete(roleId);
  },
};

export const adminMlApi = {
  triggerTraining: async (vehicleId: number) => {
    return triggerTrainingApiV1AdminMlTrainAracIdPost(vehicleId);
  },

  getQueue: async (limit = 50): Promise<AdminTrainingQueueItem[]> => {
    return getTrainingQueueApiV1AdminMlQueueGet({
      limit,
    } as unknown as Parameters<
      typeof getTrainingQueueApiV1AdminMlQueueGet
    >[0]) as unknown as AdminTrainingQueueItem[];
  },

  getModelVersions: async (vehicleId: number) => {
    return getModelVersionsApiV1AdminMlVersionsAracIdGet(vehicleId);
  },
};

export const adminMaintenanceApi = {
  getAlerts: async () => {
    return getUpcomingAlertsApiV1AdminMaintenanceAlertsGet();
  },

  markComplete: async (maintenanceId: number) => {
    return markCompleteApiV1AdminMaintenanceBakimIdCompletePatch(maintenanceId);
  },

  create: async (body: AdminMaintenanceCreateData) => {
    return createMaintenanceApiV1AdminMaintenancePost(
      body as unknown as Parameters<
        typeof createMaintenanceApiV1AdminMaintenancePost
      >[0],
    );
  },

  getVehicleHistory: async (aracId: number) => {
    return getVehicleHistoryApiV1AdminMaintenanceAracIdGet(aracId);
  },

  downloadIcs: async (bakimId: number): Promise<Blob> => {
    const response = await axiosInstance.get(
      `/api/v1/admin/maintenance/${bakimId}/ics`,
      { responseType: "blob" },
    );
    return response.data as Blob;
  },
};

export const adminHealthApi = {
  getHealth: async () => {
    return getAdminHealthApiV1AdminHealthGet();
  },

  resetCircuitBreaker: async (serviceName: string) => {
    return resetCircuitBreakerApiV1AdminHealthCircuitBreakerResetPost({
      service_name: serviceName,
    } as unknown as Parameters<
      typeof resetCircuitBreakerApiV1AdminHealthCircuitBreakerResetPost
    >[0]);
  },

  triggerBackup: async () => {
    return triggerManualBackupApiV1AdminHealthBackupTriggerPost();
  },
};

export const adminNotificationsApi = {
  getRules: async () => {
    return listRulesApiV1AdminNotificationsRulesGet();
  },

  createRule: async (body: {
    olay_tipi: string;
    kanallar: string[];
    alici_rol_id: number;
    aktif?: boolean;
  }) => {
    return createRuleApiV1AdminNotificationsRulesPost(
      body as unknown as Parameters<
        typeof createRuleApiV1AdminNotificationsRulesPost
      >[0],
    );
  },
};

export const adminFuelAccuracyApi = {
  get: async (days = 30): Promise<FuelAccuracyStats> => {
    return getFuelAccuracyApiV1AdminFuelAccuracyGet({
      days,
    } as unknown as Parameters<
      typeof getFuelAccuracyApiV1AdminFuelAccuracyGet
    >[0]) as unknown as FuelAccuracyStats;
  },
};

export const adminImportsApi = {
  getHistory: (limit = 50) =>
    importHistoryApiV1AdminImportsHistoryGet({ limit } as unknown as Parameters<
      typeof importHistoryApiV1AdminImportsHistoryGet
    >[0]),

  rollback: (jobId: number) =>
    rollbackImportApiV1AdminImportsJobIdRollbackPost(jobId),
};

export const adminAttributionApi = {
  override: async (body: AttributionOverridePayload) => {
    const { data } = await axiosInstance.post(
      "/api/v1/admin/attribution/override",
      body,
    );
    return data;
  },
};

// ── Unified adminService object (the shape the task requires) ─────────────────

export const adminService = {
  config: {
    getConfigs: adminApi.getConfigs,
    getConfig: adminApi.getConfig,
    updateConfig: adminApi.updateConfig,
  },

  users: {
    getAll: adminUsersApi.getAll,
    create: adminUsersApi.create,
    update: adminUsersApi.update,
    delete: adminUsersApi.delete,
  },

  roles: {
    getAll: adminRolesApi.getAll,
    create: adminRolesApi.create,
    update: adminRolesApi.update,
    remove: adminRolesApi.remove,
  },

  ml: {
    triggerTraining: adminMlApi.triggerTraining,
    getQueue: adminMlApi.getQueue,
    getModelVersions: adminMlApi.getModelVersions,
  },

  maintenance: {
    getAlerts: adminMaintenanceApi.getAlerts,
    markComplete: adminMaintenanceApi.markComplete,
    create: adminMaintenanceApi.create,
    getVehicleHistory: adminMaintenanceApi.getVehicleHistory,
    downloadIcs: adminMaintenanceApi.downloadIcs,
  },

  health: {
    getHealth: adminHealthApi.getHealth,
    resetCircuitBreaker: adminHealthApi.resetCircuitBreaker,
    triggerBackup: adminHealthApi.triggerBackup,
  },

  alertRules: {
    getRules: adminNotificationsApi.getRules,
    createRule: adminNotificationsApi.createRule,
  },

  fuelAccuracy: {
    get: adminFuelAccuracyApi.get,
  },
};
