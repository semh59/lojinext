export type TripStatus = "Planned" | "Completed" | "Cancelled";
export type FuelYakitDurum = "Bekliyor" | "Onaylandı" | "Reddedildi";
export type OnayDurum = "beklemede" | "onaylandi" | "reddedildi";
export type BakimTipi = "PERIYODIK" | "ARIZA" | "ACIL";

export type StatusVariant =
  | "info"
  | "success"
  | "danger"
  | "warning"
  | "neutral";

export interface StatusMeta {
  label: string;
  variant: StatusVariant;
}

export function getTripStatusMeta(status: TripStatus, lang = "tr"): StatusMeta {
  const en = lang.startsWith("en");
  const map: Record<TripStatus, StatusMeta> = {
    Planned: { label: en ? "Planned" : "Planlandı", variant: "info" },
    Completed: { label: en ? "Completed" : "Tamamlandı", variant: "success" },
    Cancelled: { label: en ? "Cancelled" : "İptal", variant: "danger" },
  };
  return map[status];
}

export function getFuelDurumMeta(
  durum: FuelYakitDurum,
  lang = "tr",
): StatusMeta {
  const en = lang.startsWith("en");
  const map: Record<FuelYakitDurum, StatusMeta> = {
    Bekliyor: { label: en ? "Pending" : "Bekliyor", variant: "warning" },
    Onaylandı: { label: en ? "Approved" : "Onaylandı", variant: "success" },
    Reddedildi: { label: en ? "Rejected" : "Reddedildi", variant: "danger" },
  };
  return map[durum];
}

export function getOnayDurumMeta(onay: OnayDurum, lang = "tr"): StatusMeta {
  const en = lang.startsWith("en");
  const map: Record<OnayDurum, StatusMeta> = {
    beklemede: {
      label: en ? "Awaiting Approval" : "Onay Bekliyor",
      variant: "warning",
    },
    onaylandi: { label: en ? "Approved" : "Onaylandı", variant: "success" },
    reddedildi: { label: en ? "Rejected" : "Reddedildi", variant: "danger" },
  };
  return map[onay];
}

export function getBakimTipiMeta(tip: BakimTipi, lang = "tr"): StatusMeta {
  const en = lang.startsWith("en");
  const map: Record<BakimTipi, StatusMeta> = {
    PERIYODIK: { label: en ? "Periodic" : "Periyodik", variant: "info" },
    ARIZA: { label: en ? "Breakdown" : "Arıza", variant: "danger" },
    ACIL: { label: en ? "Emergency" : "Acil", variant: "warning" },
  };
  return map[tip];
}

// sistem_konfig.grup is a free-text DB column (seed migration 0041 uses
// lowercase Turkish values like "rota"/"ml"/"sistem"/"anomali") — this is
// a small, known set of category tags, not something end users type, so a
// static map (with a plain fallback for anything unrecognised) is safe.
const CONFIG_GROUP_LABELS: Record<string, { tr: string; en: string }> = {
  rota: { tr: "Rota", en: "Route" },
  ml: { tr: "ML", en: "ML" },
  anomali: { tr: "Anomali", en: "Anomaly" },
  sistem: { tr: "Sistem", en: "System" },
};

export function getConfigGroupLabel(group: string, lang = "tr"): string {
  const en = lang.startsWith("en");
  const known = CONFIG_GROUP_LABELS[group.toLowerCase()];
  if (known) return en ? known.en : known.tr;
  return group.replace(/_/g, " ");
}

// dorseler.tipi raw values (TrailerModal.tsx's own <select> already maps
// these to translated option labels for the edit form — the table/card
// list just never reused that mapping and rendered the raw DB string).
const TRAILER_TIPI_LABELS: Record<string, { tr: string; en: string }> = {
  Standart: { tr: "Standart", en: "Standard" },
  Frigo: { tr: "Frigo", en: "Refrigerated" },
  Tenteli: { tr: "Tenteli", en: "Tented" },
  Damperli: { tr: "Damperli", en: "Tipper" },
  Lowbed: { tr: "Lowbed", en: "Lowbed" },
};

export function getTrailerTipiLabel(tipi: string, lang = "tr"): string {
  const en = lang.startsWith("en");
  const known = TRAILER_TIPI_LABELS[tipi];
  if (known) return en ? known.en : known.tr;
  return tipi;
}

// sofor_service.py's route-profile response pre-bakes a Turkish "label"
// string server-side (highway_dominant -> "Otoyol Ağırlıklı", etc.) — but
// it also sends the raw route_type key alongside it, so unlike the
// anomaly-reasons/coaching-caveat findings (free text with no parallel
// enum key), this one can be translated purely on the frontend.
const ROUTE_TYPE_LABELS: Record<string, { tr: string; en: string }> = {
  highway_dominant: { tr: "Otoyol Ağırlıklı", en: "Highway-heavy" },
  mountain: { tr: "Dağlık", en: "Mountainous" },
  urban: { tr: "Şehir İçi", en: "Urban" },
  mixed: { tr: "Karışık", en: "Mixed" },
};

export function getRouteTypeLabel(routeType: string, lang = "tr"): string {
  const en = lang.startsWith("en");
  const known = ROUTE_TYPE_LABELS[routeType];
  if (known) return en ? known.en : known.tr;
  return routeType;
}

// araclar.yakit_tipi enum (useVehicleData.ts's YAKIT_TIPLERI) — the vehicle
// add/edit form's <select> rendered these raw DB values directly as its own
// option labels ("DIZEL", "BENZIN", "ELEKTRIK"), never translated even
// though "LPG"/"HYBRID" happen to read the same in both languages.
const FUEL_TYPE_LABELS: Record<string, { tr: string; en: string }> = {
  DIZEL: { tr: "DIZEL", en: "DIESEL" },
  BENZIN: { tr: "BENZIN", en: "GASOLINE" },
  LPG: { tr: "LPG", en: "LPG" },
  HYBRID: { tr: "HYBRID", en: "HYBRID" },
  ELEKTRIK: { tr: "ELEKTRIK", en: "ELECTRIC" },
};

export function getFuelTypeLabel(fuelType: string, lang = "tr"): string {
  const en = lang.startsWith("en");
  const known = FUEL_TYPE_LABELS[fuelType];
  if (known) return en ? known.en : known.tr;
  return fuelType;
}

// arac_repo.py's get_maintenance_candidates() used to pre-format a single
// Turkish sentence per reason ("Yaşlı araç (18 yıl)", etc.) and join them
// with commas — always Turkish regardless of app language. It now returns
// {code, params} pairs instead; this formats each one per the active
// locale. Locale (not just language) matters here for the numeric params,
// so this takes the full useLocale() string ("tr-TR"/"en-US"), not just
// the 2-letter language.
export interface MaintenanceReasonCodeInput {
  code: string;
  params: Record<string, string | number>;
}

export function formatMaintenanceReason(
  reason: MaintenanceReasonCodeInput,
  locale = "tr-TR",
): string {
  const en = locale.startsWith("en");
  const { code, params } = reason;
  switch (code) {
    case "old_vehicle":
      return en
        ? `Old vehicle (${params.age} yr)`
        : `Yaşlı araç (${params.age} yıl)`;
    case "high_consumption": {
      const value = Number(params.value).toLocaleString(locale, {
        maximumFractionDigits: 1,
        minimumFractionDigits: 1,
      });
      return en
        ? `High consumption (${value} L/100km)`
        : `Yüksek tüketim (${value} L/100km)`;
    }
    case "high_mileage": {
      const km = Number(params.km).toLocaleString(locale);
      return en ? `High mileage (${km} km)` : `Yüksek km (${km} km)`;
    }
    case "no_maintenance_record":
      return en ? "No maintenance record" : "Bakım kaydı yok";
    case "overdue_maintenance":
      return en
        ? `Last maintenance ${params.days} days ago`
        : `Son bakım ${params.days} gün önce`;
    default:
      return code;
  }
}

// reports_studio.py's 6 static templates (Plan §5.1 — a fixed, coded list,
// not LLM/DB content) send title/description in Turkish only. The
// TemplateGallery already keys icon + category label off tmpl.id/category —
// title/description were the only fields on the same card left untranslated.
const REPORT_TEMPLATE_LABELS: Record<
  string,
  {
    tr: { title: string; description: string };
    en: { title: string; description: string };
  }
> = {
  ceo_1pager: {
    tr: {
      title: "CEO Aylık 1-Pager",
      description:
        "Tek sayfalık üst yönetim özeti — FVI, maliyet, anomali ve uyum metrikleri.",
    },
    en: {
      title: "CEO Monthly 1-Pager",
      description:
        "A one-page executive summary — FVI, cost, anomaly, and compliance metrics.",
    },
  },
  fleet_weekly: {
    tr: {
      title: "Filo Müdürü Haftalık",
      description:
        "Haftalık operasyon özeti — FVI, period karşılaştırma, cross-feature kazanım.",
    },
    en: {
      title: "Fleet Manager Weekly",
      description:
        "Weekly operations summary — FVI, period comparison, cross-feature savings.",
    },
  },
  fuel_cost_analysis: {
    tr: {
      title: "Yakıt Maliyet Analizi",
      description: "Aylık yakıt maliyet trendi ve dönem karşılaştırması.",
    },
    en: {
      title: "Fuel Cost Analysis",
      description: "Monthly fuel cost trend and period-over-period comparison.",
    },
  },
  vehicle_comparison: {
    tr: {
      title: "Araç Karşılaştırma",
      description:
        "Filodaki araçların ortalama tüketim ve maliyet karşılaştırması.",
    },
    en: {
      title: "Vehicle Comparison",
      description:
        "Average consumption and cost comparison across the fleet's vehicles.",
    },
  },
  carbon_report: {
    tr: {
      title: "Karbon Raporu",
      description: "12 ay CO₂ emisyon özeti ve hedef sapması.",
    },
    en: {
      title: "Carbon Report",
      description: "12-month CO₂ emissions summary and target deviation.",
    },
  },
  what_if: {
    tr: {
      title: "What-If Sonucu",
      description:
        "Strategic Cockpit'te çalıştırılan senaryonun PDF olarak indirilmesi.",
    },
    en: {
      title: "What-If Result",
      description: "Download the scenario run in Strategic Cockpit as a PDF.",
    },
  },
};

export function getReportTemplateMeta(
  id: string,
  lang = "tr",
): { title: string; description: string } | null {
  const en = lang.startsWith("en");
  const known = REPORT_TEMPLATE_LABELS[id];
  if (!known) return null;
  return en ? known.en : known.tr;
}

// ml_service.py's training-queue task status (app/schemas/ml_schemas.py's
// durum: str) — a fixed, closed set of English constants, but shown raw
// and uppercase-only in MLYonetimPage's table regardless of app language.
export type MlTaskDurum = "WAITING" | "RUNNING" | "COMPLETED" | "FAILED";

export function getMlTaskStatusMeta(durum: string, lang = "tr"): StatusMeta {
  const en = lang.startsWith("en");
  const map: Record<MlTaskDurum, StatusMeta> = {
    WAITING: { label: en ? "Waiting" : "Bekliyor", variant: "neutral" },
    RUNNING: { label: en ? "Running" : "Çalışıyor", variant: "warning" },
    COMPLETED: { label: en ? "Completed" : "Tamamlandı", variant: "success" },
    FAILED: { label: en ? "Failed" : "Başarısız", variant: "danger" },
  };
  const known = map[durum.toUpperCase() as MlTaskDurum];
  return known ?? { label: durum, variant: "neutral" };
}
