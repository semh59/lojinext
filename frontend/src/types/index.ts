import type { TripStatus } from "../lib/trip-status";

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip?: number;
  limit?: number;
}

export interface BaseFilters {
  skip?: number;
  limit?: number;
  search?: string;
  aktif_only?: boolean;
}

export interface Vehicle {
  id?: number;
  plaka: string;
  marka: string;
  model: string;
  yil: number;
  kapasite?: number | null;
  yakit_tipi: string;
  hedef_tuketim: number;
  aktif: boolean;
  kilometre?: number | null;
  current_lat?: number | null;
  current_lon?: number | null;
  last_update?: string | null;
  motor_no?: string | null;
  sasi_no?: string | null;
  muayene_tarihi?: string | null;
  sigorta_tarihi?: string | null;
  tank_kapasitesi?: number | null;
  maks_yuk_kapasitesi_kg?: number | null;
  bos_agirlik_kg?: number | null;
  hava_direnc_katsayisi?: number | null;
  on_kesit_alani_m2?: number | null;
  motor_verimliligi?: number | null;
  lastik_direnc_katsayisi?: number | null;
  notlar?: string | null;
}

export interface Dorse {
  id?: number;
  plaka: string;
  marka?: string | null;
  model?: string | null;
  tipi: string;
  dorse_tipi?: string | null;
  yil?: number | null;
  bos_agirlik_kg: number;
  maks_yuk_kapasitesi_kg: number;
  lastik_sayisi: number;
  dorse_lastik_direnc_katsayisi?: number | null;
  dorse_hava_direnci?: number | null;
  rolling_resistance?: number | null;
  drag_coefficient?: number | null;
  muayene_tarihi?: string | null;
  aktif: boolean;
  notlar?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface Driver {
  id?: number;
  ad_soyad: string;
  tc_no?: string | null;
  telefon?: string | null;
  ehliyet_sinifi: string;
  kan_grubu?: string | null;
  score: number;
  aktif: boolean;
  dogum_tarihi?: string | null;
  ise_giris?: string | null;
  ise_baslama?: string | null;
  sofor_score?: number | null;
  manuel_giris_serbest?: boolean | null;
  davranis_skor?: number | null;
  guvenlik_skor?: number | null;
  verimlilik_skor?: number | null;
  devir_skor?: number | null;
  manual_score?: number | null;
  notlar?: string | null;
  telegram_id?: string | null;
}

export interface FuelRecord {
  id?: number;
  arac_id: number;
  tarih: string;
  litre: number;
  fiyat_tl?: number | null;
  toplam_tutar: number;
  km_sayac: number;
  fis_no?: string | null;
  istasyon?: string | null;
  depo_durumu: "Doldu" | "Kısmi";
  durum: "Bekliyor" | "Onaylandı" | "Reddedildi";
  plaka?: string | null;
  birim_fiyat?: number | null;
}

export interface Guzergah {
  id?: number;
  ad?: string;
  cikis_yeri: string;
  varis_yeri: string;
  mesafe_km: number;
  tahmini_sure_dk?: number;
  tahmini_sure_saat?: number;
  zorluk?: "Normal" | "Orta" | "Zor";
  ascent_m?: number | null;
  descent_m?: number | null;
  cikis_lat?: number | null;
  cikis_lon?: number | null;
  varis_lat?: number | null;
  varis_lon?: number | null;
  api_mesafe_km?: number | null;
  api_sure_saat?: number | null;
  flat_distance_km?: number | null;
  tahmini_yakit_lt?: number | null;
  last_api_call?: string | null;
  otoban_mesafe_km?: number | null;
  sehir_ici_mesafe_km?: number | null;
  notlar?: string | null;
  is_active?: boolean;
  aktif?: boolean;
  varsayilan_arac_id?: number;
  varsayilan_sofor_id?: number;
}

export interface Trip {
  id?: number;
  arac_id: number;
  sofor_id: number;
  guzergah_id: number;
  dorse_id?: number | null;
  cikis_yeri: string;
  varis_yeri: string;
  mesafe_km: number;
  bos_agirlik_kg: number;
  dolu_agirlik_kg: number;
  net_kg: number;
  ton: number;
  tarih: string;
  saat: string;
  durum: TripStatus;
  gercek_tuketim?: number | null;
  tahmini_tuketim?: number | null;
  km_baslangic?: number | null;
  km_bitis?: number | null;
  ascent_m?: number | null;
  descent_m?: number | null;
  highway_km?: number | null;
  city_km?: number | null;
  flat_km?: number | null;
  weather_impact?: number | null;
  sofor_score?: number | null;
  arac_plaka?: string | null;
  sofor_ad_soyad?: string | null;
  plaka?: string | null;
  sofor_adi?: string | null;
  rota_detay?: any | null;
  tuketim?: number | null;
  sefer_no?: string | null;
  bos_sefer?: boolean | null;
  notlar?: string | null;
  flat_distance_km?: number | null;
  is_round_trip?: boolean | null;
  return_net_kg?: number | null;
  return_sefer_no?: string | null;
  otoban_mesafe_km?: number | null;
  sehir_ici_mesafe_km?: number | null;
  duration_min?: number | null;
  predicted_duration_min?: number | null;
  arac?: Vehicle | null;
  sofor?: Driver | null;
  dorse?: Dorse | null;
  version?: number | null;
  onay_durumu?: "beklemede" | "onaylandi" | "reddedildi" | null;
  onay_notu?: string | null;
}

export interface TripFormData {
  tarih: string;
  saat: string;
  arac_id: number;
  sofor_id: number;
  guzergah_id: number;
  dorse_id?: number | null;
  cikis_yeri: string;
  varis_yeri: string;
  mesafe_km: number;
  bos_agirlik_kg: number;
  dolu_agirlik_kg: number;
  net_kg: number;
  ton?: number;
  sefer_no?: string;
  bos_sefer?: boolean;
  durum: TripStatus;
  notlar?: string;
  ascent_m?: number;
  descent_m?: number;
  flat_distance_km?: number;
  baslangic_km?: number | null;
  bitis_km?: number | null;
  dagitilan_yakit?: number | null;
  tuketim?: number | null;
  is_round_trip?: boolean;
  return_net_kg?: number;
  return_sefer_no?: string;
}

export interface SeferTimelineItem {
  id: number;
  zaman: string;
  tip:
    | "CREATE"
    | "UPDATE"
    | "STATUS_CHANGE"
    | "PREDICTION_REFRESH"
    | "RECONCILIATION"
    | "DELETE";
  ozet: string;
  kullanici: string;
  changes?: Array<{ alan: string; eski: unknown; yeni: unknown }> | null;
  prediction?: {
    onceki_tahmini_tuketim?: number | null;
    tahmini_tuketim?: number | null;
    tahmin_meta?: {
      model_used?: string | null;
      model_version?: string | null;
      confidence_score?: number | null;
      fallback_triggered?: boolean | null;
    } | null;
  } | null;
  technical_details?: Record<string, unknown> | null;
}

export interface TripStatsResponse {
  total_count: number;
  completed_count: number;
  cancelled_count: number;
  planned_count: number;
  in_progress_count: number;
  total_distance_km: number;
  avg_consumption: number;
}

// Stats & Dashboard
export interface DashboardStats {
  toplam_sefer: number;
  toplam_km: number;
  toplam_yakit: number;
  filo_ortalama: number;
  aktif_arac: number;
  aktif_sofor: number;
  bugun_sefer: number;
  toplam_arac: number;
  trends: {
    sefer: number;
    km: number;
    tuketim: number;
  };
}

export interface VehicleStats {
  arac_id: number;
  plaka: string;
  toplam_sefer: number;
  toplam_km: number;
  ort_tuketim: number;
  toplam_yakit: number;
  en_iyi_tuketim?: number | null;
  en_kotu_tuketim?: number | null;
  anomali_sayisi?: number;
  eei?: number | null;
}

export interface VehicleFleetStats {
  total: number;
  active: number;
  inspection_expiring: number;
  inspection_overdue: number;
}

export interface VehicleEvent {
  id: number;
  event_type: string;
  old_status?: string | null;
  new_status?: string | null;
  triggered_by?: string | null;
  details?: string | null;
  created_at?: string | null;
}

export interface FuelStats {
  toplam_litre?: number | null;
  toplam_maliyet?: number | null;
  ort_tuketim?: number | null;
  toplam_km?: number | null;
  avg_price: number;
  kayit_sayisi?: number | null;
  ortalama_tuketim?: number | null;
  tasarruf_miktari?: number | null;
  // Aliases for compatibility
  total_consumption: number;
  total_cost: number;
  avg_consumption: number;
  total_distance: number;
}

// ML & Predictions
export interface PredictionRequest {
  arac_id: number;
  mesafe_km: number;
  ton?: number;
  ascent_m?: number;
  descent_m?: number;
  sofor_id?: number;
  sofor_score?: number;
  flat_distance_km?: number;
  zorluk?: "Normal" | "Orta" | "Zor";
  model_type?: "linear" | "xgboost" | "ensemble";
  route_analysis?: Record<string, any> | null;
}

export type PredictionFeatures = PredictionRequest;

export interface PredictionResponse {
  tahmini_tuketim: number; // L/100km
  tahmini_litre?: number; // Toplam litre (mesafe bazlı)
  model_used: "linear" | "xgboost" | "ensemble";
  status?: "success" | "failure";
  confidence_low?: number;
  confidence_high?: number;
  insight?: string;
  faktorler?: Record<string, number>;
}

export interface PredictionResult extends PredictionResponse {
  guven_araligi?: { min: number; max: number };
  tasarruf_onerisi?: string;
}

export interface ForecastItem {
  date: string;
  value: number;
  confidence_low?: number;
  confidence_high?: number;
}

export interface ForecastResponseModel {
  success: boolean;
  forecast: number[];
  forecast_dates: string[];
  confidence_low: number[];
  confidence_high: number[];
  trend: "increasing" | "stable" | "decreasing";
  vehicle_id?: number;
  series?: ForecastItem[]; // Added for widget compatibility
}

export interface ChartData {
  name: string;
  value: number | null;
  forecast?: number;
  confidenceLow?: number;
  confidenceHigh?: number;
  fullDate?: string;
}

export type TrendResponseModel = TrendAnalysis;

export interface TrendAnalysis {
  success: boolean;
  trend: "increasing" | "stable" | "decreasing";
  trend_tr: "Artıyor" | "Sabit" | "Azalıyor";
  slope: number;
  current_avg: number;
  previous_avg: number;
  details?: Array<{
    date: string;
    val: number;
  }>;
  forecast?: number[];
  confidence_high?: number[];
  confidence_low?: number[];
  dates?: string[];
}

export interface PredictionComparisonResponse {
  mae: number;
  rmse: number;
  total_compared: number;
  accuracy_distribution: {
    good: number;
    warning: number;
    error: number;
    good_pct: number;
    warning_pct: number;
    error_pct: number;
  };
  trend: Array<{
    date: string;
    actual: number;
    predicted: number;
  }>;
}

export interface EnsembleStatus {
  models: {
    physics: boolean;
    lightgbm: boolean;
    xgboost: boolean;
    gb: boolean;
    rf: boolean;
  };
  weights: Record<string, number>;
  last_train?: string;
}

// User & Auth
export interface User {
  id: number;
  email?: string;
  full_name: string;
  username?: string;
  ad?: string;
  soyad?: string;
  role: string;
  is_active: boolean;
  last_login?: string;
  created_at?: string;
  son_giris_ip?: string;
  sifre_degisim_tarihi?: string;
  rol_yetkiler?: Record<string, boolean>;
}

// Location specific re-exports or types
export interface AnalysisResponse {
  found: boolean;
  location?: {
    cikis_lat: number;
    cikis_lon: number;
    varis_lat: number;
    varis_lon: number;
  };
}

export interface CostAnalysis {
  total_cost: number;
  cost_per_km: number;
  fuel_cost_share: number;
  maintenance_share: number;
  driver_share: number;
  other_share: number;
  dates: string[];
  costs: number[];
}

export interface RoiStats {
  investment: number;
  monthly_savings: number;
  annual_savings: number;
  payback_months: number;
  annual_roi_percentage: number;
  cost_improvement_pct: number;
  target_consumption?: number;
}

export interface FuelPerformanceAnalyticsResponse {
  kpis: {
    mae: number;
    rmse: number;
    total_compared: number;
    high_deviation_ratio: number;
  };
  trend: Array<{
    date: string;
    actual: number;
    predicted: number;
  }>;
  distribution: {
    good: number;
    warning: number;
    error: number;
    good_pct: number;
    warning_pct: number;
    error_pct: number;
  };
  outliers: any[];
  low_data?: boolean;
}
