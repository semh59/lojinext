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

export function getTripStatusMeta(status: TripStatus): StatusMeta {
  const map: Record<TripStatus, StatusMeta> = {
    Planned: { label: "Planlandı", variant: "info" },
    Completed: { label: "Tamamlandı", variant: "success" },
    Cancelled: { label: "İptal", variant: "danger" },
  };
  return map[status];
}

export function getFuelDurumMeta(durum: FuelYakitDurum): StatusMeta {
  const map: Record<FuelYakitDurum, StatusMeta> = {
    Bekliyor: { label: "Bekliyor", variant: "warning" },
    Onaylandı: { label: "Onaylandı", variant: "success" },
    Reddedildi: { label: "Reddedildi", variant: "danger" },
  };
  return map[durum];
}

export function getOnayDurumMeta(onay: OnayDurum): StatusMeta {
  const map: Record<OnayDurum, StatusMeta> = {
    beklemede: { label: "Onay Bekliyor", variant: "warning" },
    onaylandi: { label: "Onaylandı", variant: "success" },
    reddedildi: { label: "Reddedildi", variant: "danger" },
  };
  return map[onay];
}

export function getBakimTipiMeta(tip: BakimTipi): StatusMeta {
  const map: Record<BakimTipi, StatusMeta> = {
    PERIYODIK: { label: "Periyodik", variant: "info" },
    ARIZA: { label: "Arıza", variant: "danger" },
    ACIL: { label: "Acil", variant: "warning" },
  };
  return map[tip];
}
