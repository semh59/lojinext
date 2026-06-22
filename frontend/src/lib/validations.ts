/**
 * Zod Validation Schemas
 *
 * Frontend form validation - mirrors backend Pydantic schemas
 * for consistent validation across the stack.
 */

import { z } from "zod";

// ============================================
// Vehicle Schemas
// ============================================

export const vehicleSchema = z.object({
  plaka: z
    .string()
    .min(3, "Plaka en az 3 karakter olmalı")
    .max(20, "Plaka en fazla 20 karakter olabilir")
    .regex(
      /^[0-9A-Z]{1,5}\s?[0-9A-Z]{1,5}\s?[0-9A-Z]{1,5}$/,
      "Geçersiz plaka formatı",
    ),
  marka: z.string().min(2, "Marka en az 2 karakter olmalı").max(50),
  model: z.string().max(50).optional(),
  yil: z
    .number()
    .int()
    .min(1990)
    .max(new Date().getFullYear() + 1),
  tank_kapasitesi: z.number().int().positive().max(5000),
  hedef_tuketim: z.number().positive().max(100).optional(),
  bos_agirlik_kg: z.number().positive().max(40000).optional(),
  hava_direnc_katsayisi: z.number().min(0.1).max(2.0).optional(),
  on_kesit_alani_m2: z.number().min(1.0).max(20.0).optional(),
  motor_verimliligi: z.number().min(0.1).max(1.0).optional(),
  lastik_direnc_katsayisi: z.number().min(0.001).max(0.1).optional(),
  maks_yuk_kapasitesi_kg: z.number().int().positive().max(50000).optional(),
  aktif: z.boolean().default(true),
  notlar: z.string().max(500).optional(),
});

export type VehicleFormData = z.infer<typeof vehicleSchema>;

// ============================================
// Driver Schemas
// ============================================

export const driverSchema = z.object({
  ad_soyad: z
    .string()
    .min(3, "İsim en az 3 karakter olmalı")
    .max(100, "İsim en fazla 100 karakter olabilir"),
  telefon: z.string().max(20).optional(),
  ise_baslama: z.string().optional(), // ISO date string
  ehliyet_sinifi: z.enum(["B", "C", "D", "E", "G"]).default("E"),
  score: z.number().min(0.1).max(2.0).default(1.0),
  manual_score: z.number().min(0.1).max(2.0).default(1.0),
  hiz_disiplin_skoru: z.number().min(0.1).max(2.0).optional(),
  agresif_surus_faktoru: z.number().min(0.1).max(2.0).optional(),
  aktif: z.boolean().default(true),
  notlar: z.string().max(500).optional(),
});

export type DriverFormData = z.infer<typeof driverSchema>;

// ============================================
// Trip Schemas
// ============================================

export const tripSchema = z.object({
  tarih: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/, "Geçersiz tarih formatı (YYYY-MM-DD)"),
  saat: z
    .string()
    .regex(/^\d{2}:\d{2}$/, "Geçersiz saat formatı (HH:MM)")
    .optional(),
  arac_id: z.number().int().positive("Araç seçilmeli"),
  sofor_id: z.number().int().positive("Şoför seçilmeli"),
  cikis_yeri: z.string().min(2).max(100),
  varis_yeri: z.string().min(2).max(100),
  mesafe_km: z.number().positive().max(10000),
  net_kg: z.number().min(0).max(100000).default(0),
  bos_sefer: z.boolean().default(false),
  ascent_m: z.number().min(0).max(10000).optional(),
  descent_m: z.number().min(0).max(10000).optional(),
  baslangic_km: z.number().min(0).optional(),
  bitis_km: z.number().min(0).optional(),
  durum: z
    .enum([
      "Bekliyor",
      "Planlandı",
      "Yolda",
      "Devam Ediyor",
      "Tamamlandı",
      "Tamam",
      "İptal",
    ])
    .default("Planlandı"),
  notlar: z.string().max(500).optional(),
  guzergah_id: z.number().int().positive().optional(),
});

export type TripFormData = z.infer<typeof tripSchema>;

// ============================================
// Fuel Schemas
// ============================================

export const fuelSchema = z.object({
  tarih: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Geçersiz tarih formatı"),
  arac_id: z.number().int().positive("Araç seçilmeli"),
  istasyon: z.string().max(100).optional(),
  fiyat_tl: z.number().positive().max(1000),
  litre: z.number().positive().max(10000),
  toplam_tutar: z.number().positive().max(1000000),
  km_sayac: z.number().int().positive().max(9999999),
  fis_no: z.string().max(50).optional(),
  depo_durumu: z.enum(["Bilinmiyor", "Doldu", "Kısmi"]).default("Bilinmiyor"),
  durum: z.enum(["Bekliyor", "Onaylandı", "Reddedildi"]).default("Bekliyor"),
});

export type FuelFormData = z.infer<typeof fuelSchema>;

// ============================================
// Location/Route Schemas
// ============================================

export const locationSchema = z.object({
  cikis_yeri: z.string().min(2).max(100),
  varis_yeri: z.string().min(2).max(100),
  mesafe_km: z.number().positive().max(10000),
  tahmini_sure_saat: z.number().positive().optional(),
  zorluk: z.enum(["Normal", "Orta", "Zor"]).default("Normal"),
  ascent_m: z.number().min(0).optional(),
  descent_m: z.number().min(0).optional(),
  cikis_lat: z.number().min(-90).max(90).optional(),
  cikis_lon: z.number().min(-180).max(180).optional(),
  varis_lat: z.number().min(-90).max(90).optional(),
  varis_lon: z.number().min(-180).max(180).optional(),
  notlar: z.string().max(500).optional(),
});

export type LocationFormData = z.infer<typeof locationSchema>;
