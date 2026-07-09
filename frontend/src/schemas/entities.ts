import { z } from "zod";
import { normalizeTripStatus } from "../lib/trip-status";

const TripStatusSchema = z.string().transform((value, ctx) => {
  const normalized = normalizeTripStatus(value);
  if (!normalized) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: `Unsupported trip status: ${value}`,
    });
    return z.NEVER;
  }
  return normalized;
});

// Base Pagination Schema
export const PaginatedResponseSchema = <T extends z.ZodTypeAny>(
  itemSchema: T,
) =>
  z.object({
    items: z.array(itemSchema),
    total: z.number(),
    skip: z.number().optional(),
    limit: z.number().optional(),
  });

// Vehicle Schema
export const VehicleSchema = z.object({
  id: z.number().optional(),
  plaka: z.string().min(1),
  marka: z.string().min(1),
  model: z.string().min(1),
  yil: z.number(),
  kapasite: z.number().optional().nullable(),
  yakit_tipi: z.string(),
  hedef_tuketim: z.number(),
  aktif: z.boolean(),
  kilometre: z.number().optional().nullable(),
  current_lat: z.number().optional().nullable(),
  current_lon: z.number().optional().nullable(),
  last_update: z.string().optional().nullable(),
  motor_no: z.string().optional().nullable(),
  sasi_no: z.string().optional().nullable(),
  muayene_tarihi: z.string().optional().nullable(),
  sigorta_tarihi: z.string().optional().nullable(),
  tank_kapasitesi: z.number().optional().nullable(),
  maks_yuk_kapasitesi_kg: z.number().optional().nullable(),
  bos_agirlik_kg: z.number().optional().nullable(),
  hava_direnc_katsayisi: z.number().optional().nullable(),
  on_kesit_alani_m2: z.number().optional().nullable(),
  motor_verimliligi: z.number().optional().nullable(),
  lastik_direnc_katsayisi: z.number().optional().nullable(),
  notlar: z.string().optional().nullable(),
});

// Driver Schema
export const DriverSchema = z.object({
  id: z.number().optional(),
  ad_soyad: z.string().min(1),
  tc_no: z.string().optional().nullable(),
  telefon: z.string().optional().nullable(),
  ehliyet_sinifi: z.string(),
  kan_grubu: z.string().optional().nullable(),
  score: z.number(),
  aktif: z.boolean(),
  dogum_tarihi: z.string().optional().nullable(),
  ise_giris: z.string().optional().nullable(),
  ise_baslama: z.string().optional().nullable(),
  sofor_score: z.number().optional().nullable(),
  manuel_giris_serbest: z.boolean().optional().nullable(),
  davranis_skor: z.number().optional().nullable(),
  guvenlik_skor: z.number().optional().nullable(),
  verimlilik_skor: z.number().optional().nullable(),
  devir_skor: z.number().optional().nullable(),
  manual_score: z.number().optional().nullable(),
  notlar: z.string().optional().nullable(),
});

// Dorse (Trailer) Schema
export const DorseSchema = z.object({
  id: z.number().optional(),
  plaka: z.string().min(1),
  marka: z.string().optional().nullable(),
  model: z.string().optional().nullable(),
  tipi: z.string(),
  yil: z.number().optional().nullable(),
  bos_agirlik_kg: z.number(),
  maks_yuk_kapasitesi_kg: z.number(),
  lastik_sayisi: z.number(),
  dorse_lastik_direnc_katsayisi: z.number().optional().nullable(),
  dorse_hava_direnci: z.number().optional().nullable(),
  muayene_tarihi: z.string().optional().nullable(),
  aktif: z.boolean(),
  notlar: z.string().optional().nullable(),
});

// Guzergah (Route) Schema
export const GuzergahSchema = z.object({
  id: z.number(),
  cikis_yeri: z.string(),
  varis_yeri: z.string(),
  mesafe_km: z.number(),
  tahmini_sure_saat: z.number(),
  // Backend (lokasyon.py) zorluk is a free Optional[str] that can be null or a
  // value outside this enum ("Düz"/"Hafif Eğimli"/"Dik/Dağlık") → a strict enum
  // failed the ENTIRE locations list (Sentry LOJINEXT-19Q). .catch keeps the
  // type stable and renders the list instead of throwing on unexpected values.
  zorluk: z.enum(["Normal", "Orta", "Zor"]).catch("Normal"),
  ascent_m: z.number().optional().nullable(),
  descent_m: z.number().optional().nullable(),
  cikis_lat: z.number().optional().nullable(),
  cikis_lon: z.number().optional().nullable(),
  varis_lat: z.number().optional().nullable(),
  varis_lon: z.number().optional().nullable(),
  api_mesafe_km: z.number().optional().nullable(),
  api_sure_saat: z.number().optional().nullable(),
  flat_distance_km: z.number().optional().nullable(),
  tahmini_yakit_lt: z.number().optional().nullable(),
  last_api_call: z.string().optional().nullable(),
  otoban_mesafe_km: z.number().optional().nullable(),
  sehir_ici_mesafe_km: z.number().optional().nullable(),
  notlar: z.string().optional().nullable(),
  aktif: z.boolean().optional().nullable(),
  source: z.string().optional().nullable(),
  is_corrected: z.boolean().optional().nullable(),
  correction_reason: z.string().optional().nullable(),
});

// Trip Schema
export const TripSchema = z.object({
  id: z.number().optional(),
  arac_id: z.number(),
  sofor_id: z.number(),
  guzergah_id: z.number(),
  dorse_id: z.number().optional().nullable(),
  cikis_yeri: z.string(),
  varis_yeri: z.string(),
  mesafe_km: z.number(),
  bos_agirlik_kg: z.number(),
  dolu_agirlik_kg: z.number(),
  net_kg: z.number(),
  ton: z.number(),
  tarih: z.string(),
  // Backend (sefer.py) returns saat as Optional[str] (HH:MM or null). A bare
  // z.string() rejected null → "Invalid input" failed the ENTIRE trips list
  // (Sentry LOJINEXT-19T) → trips/suggestions never rendered. .catch("") keeps
  // the type `string` (no TS cascade) and renders the list.
  saat: z.string().catch(""),
  durum: TripStatusSchema,
  gercek_tuketim: z.number().optional().nullable(),
  tahmini_tuketim: z.number().optional().nullable(),
  km_baslangic: z.number().optional().nullable(),
  km_bitis: z.number().optional().nullable(),
  ascent_m: z.number().optional().nullable(),
  descent_m: z.number().optional().nullable(),
  highway_km: z.number().optional().nullable(),
  city_km: z.number().optional().nullable(),
  flat_km: z.number().optional().nullable(),
  weather_impact: z.number().optional().nullable(),
  sofor_score: z.number().optional().nullable(),
  arac_plaka: z.string().optional().nullable(),
  sofor_ad_soyad: z.string().optional().nullable(),
  plaka: z.string().optional().nullable(), // UI Alias
  sofor_adi: z.string().optional().nullable(), // UI Alias
  sefer_no: z.string().optional().nullable(),
  bos_sefer: z.boolean().optional().nullable(),
  notlar: z.string().optional().nullable(),
  flat_distance_km: z.number().optional().nullable(),
  is_round_trip: z.boolean().optional().nullable(),
  return_net_kg: z.number().optional().nullable(),
  return_sefer_no: z.string().optional().nullable(),
  otoban_mesafe_km: z.number().optional().nullable(),
  sehir_ici_mesafe_km: z.number().optional().nullable(),
  duration_min: z.number().optional().nullable(),
  predicted_duration_min: z.number().optional().nullable(),
  version: z.number().optional().nullable(),
});

// Fuel Record Schema
export const FuelRecordSchema = z.object({
  id: z.number().optional(),
  arac_id: z.number(),
  tarih: z.string(),
  litre: z.number(),
  fiyat_tl: z.number().optional().nullable(),
  toplam_tutar: z.number(),
  km_sayac: z.number(),
  fis_no: z.string().optional().nullable(),
  istasyon: z.string().optional().nullable(),
  depo_durumu: z.enum(["Doldu", "Kısmi"]),
  durum: z.enum(["Bekliyor", "Onaylandı", "Reddedildi"]),
  plaka: z.string().optional().nullable(),
  birim_fiyat: z.number().optional().nullable(),
});

// Stats & Timeline Schemas
export const SeferTimelineItemSchema = z.object({
  id: z.number(),
  zaman: z.string(),
  tip: z.enum([
    "CREATE",
    "UPDATE",
    "STATUS_CHANGE",
    "PREDICTION_REFRESH",
    "RECONCILIATION",
    "DELETE",
  ]),
  ozet: z.string(),
  kullanici: z.string(),
  changes: z
    .array(z.object({ alan: z.string(), eski: z.any(), yeni: z.any() }))
    .optional()
    .nullable(),
  prediction: z
    .object({
      onceki_tahmini_tuketim: z.number().optional().nullable(),
      tahmini_tuketim: z.number().optional().nullable(),
      tahmin_meta: z
        .object({
          model_used: z.string().optional().nullable(),
          model_version: z.string().optional().nullable(),
          confidence_score: z.number().optional().nullable(),
          fallback_triggered: z.boolean().optional().nullable(),
        })
        .optional()
        .nullable(),
    })
    .optional()
    .nullable(),
});

export const DashboardStatsSchema = z.object({
  toplam_sefer: z.number(),
  toplam_km: z.number(),
  toplam_yakit: z.number(),
  filo_ortalama: z.number(),
  aktif_arac: z.number(),
  aktif_sofor: z.number(),
  bugun_sefer: z.number(),
  toplam_arac: z.number(),
  trends: z.object({
    sefer: z.number(),
    km: z.number(),
    tuketim: z.number(),
  }),
});

export const VehicleStatsSchema = z.object({
  arac_id: z.number(),
  plaka: z.string(),
  toplam_sefer: z.number(),
  toplam_km: z.number(),
  ort_tuketim: z.number(),
  toplam_yakit: z.number(),
  en_iyi_tuketim: z.number().optional().nullable(),
  en_kotu_tuketim: z.number().optional().nullable(),
  anomali_sayisi: z.number().optional(),
  eei: z.number().optional().nullable(),
});

export const FuelStatsSchema = z.object({
  toplam_litre: z.number().nullable().optional(),
  toplam_maliyet: z.number().nullable().optional(),
  ort_tuketim: z.number().nullable().optional(),
  toplam_km: z.number().nullable().optional(),
  avg_price: z.number(),
  kayit_sayisi: z.number().optional().nullable(),
  ortalama_tuketim: z.number().optional().nullable(),
  tasarruf_miktari: z.number().optional().nullable(),
  total_consumption: z.number(),
  total_cost: z.number(),
  avg_consumption: z.number(),
  total_distance: z.number(),
});

export const TripStatsSchema = z.object({
  total_count: z.number(),
  completed_count: z.number(),
  cancelled_count: z.number(),
  planned_count: z.number(),
  in_progress_count: z.number(),
  total_distance_km: z.number(),
  avg_consumption: z.number(),
});

// Export types derived from schemas
export type VehicleZod = z.infer<typeof VehicleSchema>;
export type DriverZod = z.infer<typeof DriverSchema>;
export type DorseZod = z.infer<typeof DorseSchema>;
export type TripZod = z.infer<typeof TripSchema>;
export type FuelRecordZod = z.infer<typeof FuelRecordSchema>;
export type TripStatsZod = z.infer<typeof TripStatsSchema>;
export type GuzergahZod = z.infer<typeof GuzergahSchema>;
export type DashboardStatsZod = z.infer<typeof DashboardStatsSchema>;
export type SeferTimelineItemZod = z.infer<typeof SeferTimelineItemSchema>;
