export const locationsPageText = {
  heading: "Lokasyon ve Rota Yönetimi",
  description:
    "Kayıtlı güzergahları, zorluk seviyelerini ve rota analizlerini yönetin.",
  addRoute: "Yeni Güzergah",
  deleteConfirm: (origin: string, destination: string) =>
    `${origin} - ${destination} güzergahını silmek istediğinize emin misiniz?`,
  notifications: {
    analysisUpdated: "Analiz güncellendi",
    analysisFailed: "Analiz yapılamadı.",
    updateSuccess: "Güzergah güncellendi.",
    createSuccess: "Yeni güzergah oluşturuldu.",
    deleteSuccess: "Güzergah silindi.",
    deleteFailed: "Güzergah silinemedi.",
    saveFailed: "İşlem başarısız oldu.",
    templateFailed: "Şablon indirilemedi.",
    exportFailed: "Dışa aktarma başarısız.",
    importSuccess: (count: number) => `${count} güzergah yüklendi.`,
    importFailed: "Dosya yüklenemedi.",
  },
  downloadTemplateFileName: "guzergah_sablonu.xlsx",
  exportFileName: "guzergahlar.xlsx",
  kpis: {
    totalRoutes: {
      label: "Toplam Rota",
      hint: "Bu sayfadaki kayıtlar",
    },
    analyzedRoutes: {
      label: "Analizli Rota",
      hint: "Rota analizi mevcut",
    },
    averageDistance: {
      label: "Ortalama Mesafe",
      hint: "Sayfa ortalaması",
    },
    highDifficulty: {
      label: "Zor Seviye",
      hint: "Yüksek zorluk etiketi",
    },
  },
  visibility: {
    title: "Operasyonel Görünürlük",
    description:
      "Bu ekran yalnız kayıtlı rota ve analiz verilerini gösterir. Canlı harita veya simüle telemetri kullanılmaz.",
    readyCount: (count: number) => `${count} rota için analiz verisi hazır`,
    empty: "Henüz gösterilecek rota kaydı bulunmuyor",
  },
  searchPlaceholder: "Güzergah veya şehir ara...",
  difficultyPlaceholder: "Zorluk seviyesi",
  difficultyOptions: {
    normal: "Normal",
    medium: "Orta",
    hard: "Zor",
  },
  pagination: {
    summary: (total: number, shown: number) =>
      `Toplam ${total} kayıttan ${shown} tanesi gösteriliyor`,
    previous: "Geri",
    next: "İleri",
  },
} as const;

export const locationListText = {
  headers: {
    routeInfo: "Güzergah Bilgisi",
    destination: "Varış Noktası",
    distance: "Mesafe",
    fuelEstimate: "Tahmini Yakıt",
    difficulty: "Zorluk Seviyesi",
    analysis: "Teknik Analiz",
    actions: "İşlemler",
  },
  fuelEstimateTooltip:
    "Tahmini yakıt = mesafe × araç ortalama tüketim × yük katsayısı (route_analysis.fuel_estimate_cache).",
  emptyTitle: "Güzergah Bulunamadı",
  emptyDescription:
    "Sistemde henüz kayıtlı bir operasyonel güzergah bulunmuyor. Lütfen ilk planlamanızı oluşturun.",
  addRoute: "Yeni Güzergah Tanımla",
  listTitle: "Sistem Kayıtlı Güzergahlar",
  difficulty: {
    hard: "Dağlık / Zor",
    medium: "Eğimli / Orta",
    easy: "Düz / Kolay",
  },
  source: {
    verified: "Güncel Harita Verisi",
    standard: "Standart Rota Verisi",
    corrected: "Düzeltildi",
  },
  freshness: {
    never: "Hiç analiz edilmedi",
    stale: (days: number) => `${days}g önce`,
    old: (days: number) => `${days}g önce`,
    fresh: (days: number) => (days === 0 ? "Bugün" : `${days}g önce`),
  },
  analysisMetrics: {
    ascent: "Çıkış",
    descent: "İniş",
  },
  actions: {
    analyze: "Analiz",
    edit: "Düzenle",
    delete: "Sil",
  },
} as const;

export const routeAnalysisCardText = {
  summaryTitle: "Güzergah Özeti",
  summarySubtitle: "Yol karakteri ve eğim dağılımı",
  sourceChip: "Doğrulanmış Rota Analizi",
  roadDistribution: "Yol Karakteri Dağılımı",
  totalRoute: "Toplam Rota",
  roadTypes: {
    highway: "Otoyol",
    stateRoad: "Devlet Yolu",
    urban: "Şehir İçi",
  },
  roadSpeeds: {
    highway: "85 km/h",
    stateRoad: "65 km/h",
    urban: "35 km/h",
  },
  terrainTitle: "Eğim ve Topografya",
  steepness: {
    flat: "Düz",
    uphill: "Çıkış",
    downhill: "İniş",
  },
  tooltipRatio: "Oran",
  summaryBoxTitle: "Analiz Özeti",
  summaryBoxDescription: (highwayRatio: number) =>
    `Bu rotada toplam yolun %${Math.round(
      highwayRatio * 100,
    )} bölümü otoyol olarak sınıflandırıldı. Eğim, çıkış ve iniş dağılımı yakıt tüketimi değerlendirmesinde doğrudan kullanılır.`,
} as const;

export const analysisModalText = {
  title: "Rota Analizi",
  loading: "OpenRouteService ile analiz yapılıyor...",
  empty: "Bu rota için henüz detaylı analiz yapılmamış.",
  actions: {
    start: "Analizi Başlat",
    close: "Kapat",
    rerun: "Yeniden Analiz Et",
    calibrate: "Sefer ile Kalibre Et",
  },
  routeSummary: (origin: string, destination: string, distanceKm: number) =>
    `${origin} → ${destination} (${distanceKm} km)`,
} as const;

export const locationFormText = {
  titles: {
    edit: "Güzergahı Düzenle",
    create: "Yeni Güzergah Ekle",
  },
  sections: {
    points: "Nokta Seçimi",
    summary: "Rota Özeti",
  },
  inputs: {
    originSearchLabel: "Çıkış yeri arama",
    destinationSearchLabel: "Varış yeri arama",
    originPlaceholder: "Depo, fabrika veya tam adres ara",
    destinationPlaceholder: "Depo, fabrika veya tam adres ara",
    searching: "Aranıyor...",
    originCoordinates: "Çıkış",
    destinationCoordinates: "Varış",
    recalculate: "Rotayı Yeniden Hesapla",
    distanceLabel: "Mesafe (km)",
    durationLabel: "Tahmini süre",
    ascentLabel: "Tırmanış",
    descentLabel: "İniş",
    distributionTitle: "Yol Dağılımı",
    highway: "Otoban",
    otherRoads: "Şehir içi / diğer",
    notesPlaceholder: "Güzergah ile ilgili operasyonel notlar",
  },
  actions: {
    cancel: "İptal",
    save: "Kaydet",
    update: "Güncelle",
  },
  toasts: {
    selectBothEndpoints: "Lütfen her iki nokta için listeden bir sonuç seçin",
    routeCalculated: "Rota bilgileri hesaplandı",
    routeCalculationFailed: "Rota hesaplanırken bir hata oluştu",
    saveFailed: "Kayıt sırasında bir hata oluştu",
  },
  validation: {
    originRequired: "Çıkış noktası seçilmelidir",
    destinationRequired: "Varış noktası seçilmelidir",
    distancePositive: "Mesafe 0'dan büyük olmalıdır",
    durationRange: "Süre 0 ile 48 saat arasında olmalıdır",
    ascentRange: "Tırmanış 0 ile 10000 arasında olmalıdır",
    descentRange: "İniş 0 ile 10000 arasında olmalıdır",
    notesMax: "Notlar en fazla 500 karakter olabilir",
  },
} as const;
