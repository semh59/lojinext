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
