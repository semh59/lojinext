export const tripPlannerText = {
  tabLabel: "Akıllı Plan",
  title: "Akıllı Sefer Planlama",
  intro:
    'Tarih + güzergah seçtikten sonra "Önerileri Getir" ile sistem 3 araç + 3 şoför adayı sunacak.',
  fetchButton: "Önerileri Getir",
  retryButton: "Tekrar Dene",
  loading: "Adaylar değerlendiriliyor…",
  sections: {
    vehicles: "Önerilen Araçlar",
    drivers: "Önerilen Şoförler",
  },
  errors: {
    missingRoute: "Önce tarih ve güzergah seçin.",
    fetch: "Öneriler alınamadı. Tekrar deneyin.",
    flagOff: "Sefer planlama sihirbazı devre dışı.",
    forbidden: "Bu işlem için yetkiniz yok.",
    empty: "Bu kriterlere uygun aday bulunamadı. Manuel formu kullanın.",
  },
  risk: {
    low: "Hava: Düşük risk",
    medium: "Hava: Orta risk",
    high: "Hava: Yüksek risk",
    unknown: "Hava: Veri yok",
  },
  routeTypeLabels: {
    highway_dominant: "Otoyol Ağırlıklı",
    mountain: "Dağlık",
    urban: "Şehir İçi",
    mixed: "Karışık",
  } as const,
  coldStart: {
    vehicle: "Yeni araç",
    driver: "Yeni şoför",
  },
  card: {
    score: "Skor",
    predicted: "Tahmini tüketim",
    liters: "L",
    age: "Yaş",
    similar: "Benzer sefer",
    whyButton: "Neden bu?",
  },
  selected: "Seçildi",
  selectAndContinue: "Seç ve Devam",
  confirmSelection: "Seçilen araç + şoför detay adımına aktarılacak.",
  xai: {
    title: "Neden bu öneri?",
    vehicleSubtitle: "Araç skoru kırılımı",
    driverSubtitle: "Şoför skoru kırılımı",
    totalScore: "Toplam skor",
    weightSuffix: "ağırlık",
    vehicleFactors: {
      fuel: "Yakıt verimliliği",
      route_history: "Güzergah tarihi",
      vehicle_health: "Araç sağlığı",
      availability: "Müsaitlik",
    },
    driverFactors: {
      route_type_perf: "Güzergah tipi performansı",
      overall_hybrid: "Hibrit skor",
      availability: "Müsaitlik",
    },
    reasonsHeading: "Sebepler",
    noReasons: "Sebep listesi boş.",
    close: "Kapat",
    meta: {
      similar: "Benzer sefer sayısı",
      predicted: "Tahmini tüketim",
      age: "Araç yaşı",
      deviation: "Sapma",
      routeType: "Güzergah tipi",
    },
  },
} as const;

export type TripPlannerText = typeof tripPlannerText;
