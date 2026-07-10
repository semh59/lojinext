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
