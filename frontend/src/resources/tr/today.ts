export const todayText = {
  pageTitle: "Bugün",
  pageSubtitle: "Acil eylem listesi + bekleyen aksiyonlar",

  sections: {
    critical: "Acil Eylem",
    pending: "Bekleyen Aksiyon",
    empty: "Bugün için acil eylem yok",
  },

  tabs: {
    all: "Tümü",
    anomaly: "Anomali",
    maintenance: "Bakım",
    investigation: "Soruşturma",
  } as const,

  severity: {
    critical: "Kritik",
    high: "Yüksek",
    medium: "Orta",
    low: "Düşük",
  } as const,

  category: {
    anomaly: "Anomali",
    maintenance: "Bakım",
    investigation: "Soruşturma",
    telegram_approval: "Onay",
    active_trip: "Aktif Sefer",
  } as const,

  counters: {
    activeTrips: "Aktif sefer",
    completedToday: "Bugün tamamlanan",
  },

  quickActions: {
    title: "Hızlı Erişim",
    newTrip: "Sefer Planla",
    anomalies: "Anomaliler",
    drivers: "Şoförler",
    executive: "Strategic Cockpit",
  },

  errors: {
    loadFailed: "Liste yüklenemedi",
    flagOff: "Reports v2 devre dışı",
  },
} as const;

export type TodayText = typeof todayText;
