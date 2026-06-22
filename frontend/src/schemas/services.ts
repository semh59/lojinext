import { z } from "zod";

// ─── AI Service Schemas ───────────────────────────────────────────────────────

export const ChatResponseSchema = z.object({
  response: z.string(),
  timestamp: z.string(),
});

export const AIStatusSchema = z.object({
  is_ready: z.boolean(),
  progress: z.object({
    status: z.string(),
    // Backend get_progress() can return percent as null/missing (e.g. idle, no
    // training) → bare z.number() failed validation (Sentry 19S). Coerce +
    // catch so a weird value renders 0% instead of breaking the AI status panel.
    percent: z.coerce.number().catch(0),
    speed: z.string().optional().default(""),
  }),
});

// ─── Weather Service Schemas ──────────────────────────────────────────────────

export const WeatherForecastSchema = z
  .object({
    temperature: z.number().optional(),
    humidity: z.number().optional(),
    wind_speed: z.number().optional(),
    condition: z.string().optional(),
    forecast: z.array(z.record(z.string(), z.unknown())).optional(),
  })
  .passthrough();

export const WeatherTripImpactSchema = z
  .object({
    impact_score: z.number().optional(),
    fuel_impact_factor: z.number().optional(),
    recommendations: z.array(z.string()).optional(),
    weather_conditions: z.record(z.string(), z.unknown()).optional(),
  })
  .passthrough();

export const WeatherDashboardSummarySchema = z
  .object({
    current: z.record(z.string(), z.unknown()).optional(),
    alerts: z.array(z.string()).optional(),
  })
  .passthrough();

// ─── Auth Service Schemas ─────────────────────────────────────────────────────

export const LoginResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.string(),
});

export const MeResponseSchema = z
  .object({
    id: z.number(),
    email: z.string(),
    ad_soyad: z.string(),
    aktif: z.boolean(),
    rol_id: z.number().optional().nullable(),
    rol: z
      .object({
        id: z.number().optional(),
        ad: z.string().optional(),
        yetkiler: z.record(z.string(), z.boolean()).optional(),
      })
      .optional()
      .nullable(),
    created_at: z.string().optional().nullable(),
    updated_at: z.string().optional().nullable(),
    son_giris: z.string().optional().nullable(),
    son_giris_ip: z.string().optional().nullable(),
    sifre_degisim_tarihi: z.string().optional().nullable(),
  })
  .passthrough();

// ─── Report Service Schemas ───────────────────────────────────────────────────

// Matches DashboardStats interface in types/index.ts (Turkish field names)
export const DashboardStatsSchema = z
  .object({
    toplam_sefer: z.number(),
    toplam_km: z.number(),
    toplam_yakit: z.number(),
    filo_ortalama: z.number(),
    aktif_arac: z.number(),
    aktif_sofor: z.number(),
    bugun_sefer: z.number(),
    toplam_arac: z.number(),
    in_progress_count: z.number().optional(),
    trends: z
      .object({
        sefer: z.number(),
        km: z.number(),
        tuketim: z.number(),
      })
      .optional(),
  })
  .passthrough();

export const ConsumptionTrendPointSchema = z.object({
  month: z.string(),
  consumption: z.number(),
});

export const MonthlyCostTrendSchema = z
  .object({
    month: z.number(),
    year: z.number(),
    label: z.string(),
    fuel_cost: z.number(),
    fuel_liters: z.number(),
    trip_count: z.number(),
    total_distance: z.number(),
    cost_per_km: z.number(),
    fuel: z.number().optional(),
    maintenance: z.number().optional(),
  })
  .passthrough();

export const VehicleCostComparisonSchema = z
  .object({
    arac_id: z.number(),
    plaka: z.string(),
    fuel_cost: z.number(),
    avg_consumption: z.number(),
    average_consumption: z.number().optional(),
    trip_count: z.number(),
    total_distance: z.number(),
    unavailable: z.boolean().optional(),
    error_code: z.string().optional(),
  })
  .passthrough();

// Matches RoiStats interface in types/index.ts
export const RoiStatsSchema = z.object({
  investment: z.number().optional(),
  monthly_savings: z.number().optional(),
  annual_savings: z.number().optional(),
  payback_months: z.number().optional(),
  annual_roi_percentage: z.number().optional(),
  cost_improvement_pct: z.number().optional(),
  target_consumption: z.number().optional(),
  // Legacy field names from older API versions
  roi_years: z.number().optional(),
});

// Matches SavingsStats type in ROICalculator.tsx
export const SavingsPotentialSchema = z.object({
  current_consumption: z.number().optional(),
  target_consumption: z.number().optional(),
  current_cost: z.number().optional(),
  target_cost: z.number().optional(),
  potential_savings: z.number().optional(),
  savings_percentage: z.number().optional(),
  annual_projection: z.number().optional(),
  // Legacy field names from older API versions
  current_avg: z.number().optional(),
  target_avg: z.number().optional(),
  potential_savings_liters: z.number().optional(),
  potential_savings_tl: z.number().optional(),
});

// ─── Preference Service Schemas ───────────────────────────────────────────────

export const PreferenceSchema = z.object({
  id: z.number(),
  modul: z.string(),
  ayar_tipi: z.string(),
  deger: z.unknown(),
  ad: z.string().optional().nullable(),
  is_default: z.boolean(),
  created_at: z.string(),
  updated_at: z.string(),
});

// ─── Prediction Service Schemas ───────────────────────────────────────────────

export const PredictionComparisonSchema = z.object({
  mae: z.number(),
  rmse: z.number(),
  accuracy_distribution: z.object({
    good: z.number(),
    warning: z.number(),
    error: z.number(),
    good_pct: z.number(),
    warning_pct: z.number(),
    error_pct: z.number(),
  }),
  trend: z.array(
    z.object({
      date: z.string(),
      actual: z.number(),
      predicted: z.number(),
    }),
  ),
  total_compared: z.number(),
});

export const PredictionResultSchema = z
  .object({
    tahmini_tuketim: z.number().optional(),
    prediction_liters: z.number().optional(),
    confidence_score: z.number().optional(),
    model_used: z.string().optional(),
    components: z.record(z.string(), z.unknown()).optional(),
  })
  .passthrough();

export const PredictionEnqueueResponseSchema = z.object({
  task_id: z.string(),
  status: z.string(),
});

export const PredictionStatusResponseSchema = z.object({
  task_id: z.string(),
  status: z.string(),
  answer: z.string().optional(),
  error: z.string().optional(),
  finished_at: z.string().optional(),
});

export const EnsembleStatusResponseSchema = z.object({
  models: z.record(z.string(), z.boolean()),
  weights: z.record(z.string(), z.number()),
  sklearn_available: z.boolean(),
  lightgbm_available: z.boolean(),
  xgboost_available: z.boolean(),
  total_models: z.number(),
});

// ─── Admin Service Schemas ────────────────────────────────────────────────────

export const AdminConfigItemSchema = z.object({
  anahtar: z.string(),
  deger: z.unknown(),
  tip: z.string(),
  birim: z.string().optional().nullable(),
  min_deger: z.number().optional().nullable(),
  max_deger: z.number().optional().nullable(),
  grup: z.string(),
  aciklama: z.string().optional().nullable(),
  yeniden_baslat: z.boolean(),
});

export const AdminUserRecordSchema = z
  .object({
    id: z.number(),
    email: z.string().optional().nullable(),
    ad_soyad: z.string(),
    aktif: z.boolean(),
    rol_id: z.number().optional().nullable(),
    son_giris: z.string().optional().nullable(),
    rol: z
      .object({
        id: z.number().optional(),
        ad: z.string().optional(),
        yetkiler: z.record(z.string(), z.boolean()).optional(),
      })
      .optional()
      .nullable(),
  })
  .passthrough();

export const AdminRoleRecordSchema = z.object({
  id: z.number(),
  ad: z.string(),
  yetkiler: z.record(z.string(), z.boolean()),
});

export const AdminTrainingQueueItemSchema = z.object({
  id: z.number(),
  arac_id: z.number().optional().nullable(),
  durum: z.string().optional().nullable(),
  metrics: z
    .object({
      algorithm: z.string().optional(),
      rmse: z.number().optional(),
    })
    .optional()
    .nullable(),
  training_time_seconds: z.number().optional().nullable(),
  error_message: z.string().optional().nullable(),
  trigger_reason: z.string().optional().nullable(),
  created_at: z.string(),
});

export const AdminImportHistoryItemSchema = z
  .object({
    id: z.number().optional(),
    status: z.string().optional(),
    created_at: z.string().optional(),
    file_name: z.string().optional(),
  })
  .passthrough();

// Typed to match fields accessed by OverviewPage and SistemSaglikPage
export const AdminHealthSchema = z
  .object({
    status: z.string().optional(),
    uptime: z.number().optional(),
    components: z
      .object({
        database: z
          .object({
            status: z.string().optional(),
          })
          .passthrough()
          .optional(),
        redis: z
          .object({
            status: z.string().optional(),
          })
          .passthrough()
          .optional(),
      })
      .passthrough()
      .optional(),
    circuit_breakers: z
      .array(
        z
          .object({
            name: z.string().optional(),
            state: z.string().optional(),
          })
          .passthrough(),
      )
      .optional(),
    backups: z
      .object({
        status: z.string().optional(),
        last_backup: z.string().optional().nullable(),
      })
      .optional(),
  })
  .passthrough();

export const AdminMaintenanceAlertSchema = z
  .object({
    id: z.number().optional(),
    arac_id: z.number().optional(),
    tip: z.string().optional(),
    aciklama: z.string().optional(),
    olusturma_tarihi: z.string().optional(),
  })
  .passthrough();

export const AdminNotificationRuleSchema = z
  .object({
    id: z.number().optional(),
    olay_tipi: z.string(),
    kanallar: z.array(z.string()),
    alici_rol_id: z.number(),
    aktif: z.boolean().optional(),
  })
  .passthrough();
