export const fleetPageText = {
  heading: "Filo Yönetimi",
  description:
    "Araç parkuru, sürücü kadrosu ve dorse envanterini buradan takip edin.",
  tabs: {
    vehicles: "Araçlar",
    drivers: "Sürücüler",
    trailers: "Dorseler",
  },
} as const;

export const fleetInsightsText = {
  labels: {
    vehicles: "Araç",
    drivers: "Şoför",
    trailers: "Dorse",
    fallback: "Kayıt",
  },
  cards: {
    total: (label: string) => `Toplam ${label}`,
    active: (label: string) => `Aktif ${label}`,
    trips: "Bu Ay Sefer",
    recordsUnit: "kayıt",
    inspectionWarning: "Muayene Uyarısı",
    vehicleUnit: "araç",
    inspectionOk: "Muayene sorunsuz",
    inspectionHint: (expiring: number, overdue: number) =>
      overdue > 0
        ? `${overdue} araç muayene süresi geçmiş`
        : `${expiring} araç 30 gün içinde`,
  },
} as const;
