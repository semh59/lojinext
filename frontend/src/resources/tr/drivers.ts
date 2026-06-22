export const driverModuleText = {
  licenseOptions: ["", "B", "C", "CE", "D", "D1E", "E", "G"],
  notifications: {
    successTitle: "Başarılı",
    updateTitle: "Güncellendi",
    createTitle: "Eklendi",
    scoreUpdatedTitle: "Puan Güncellendi",
    errorTitle: "Hata",
    deleteSoft: "Şoför pasife çekildi.",
    deleteHard: "Şoför silindi.",
    updateDescription: "Şoför bilgileri başarıyla güncellendi.",
    createDescription: "Yeni şoför başarıyla eklendi.",
    saveFallback: "İşlem sırasında bir hata oluştu.",
    scoreFallback: "Puan güncelleme başarısız.",
    genericFallback: "İşlem başarısız.",
    exportSuccess: "Excel dosyası hazırlandı.",
    exportError: "Dışa aktarma başarısız.",
    templateSuccess: "Şablon indirildi.",
    templateError: "Şablon indirilemedi.",
    importSuccess: "Şoförler başarıyla içe aktarıldı.",
    importSuccessWithCounts: (inserted: number, errorCount: number) =>
      errorCount > 0
        ? `${inserted} şoför eklendi, ${errorCount} satır atlandı.`
        : `${inserted} şoför başarıyla içe aktarıldı.`,
    importError: "İçe aktarma başarısız.",
    bulkDeleteSuccess: (count: number) => `${count} şoför pasife alındı.`,
  },
  confirm: {
    delete: (name: string) =>
      `${name} adlı şoförü kalıcı olarak silmek istediğinize emin misiniz?`,
    deactivate: (name: string) =>
      `${name} adlı şoförü pasife çekmek istediğinize emin misiniz?`,
    bulkDelete: (count: number) =>
      `${count} şoförü pasife almak istediğinize emin misiniz? Geri almak için tekrar aktif etmeniz gerekir.`,
  },
  files: {
    exportPrefix: "soforler_export",
    templateName: "sofor_yukleme_sablonu.xlsx",
  },
} as const;

export const driverHeaderText = {
  addButton: "Yeni Şoför Ekle",
} as const;

export const driverFilterText = {
  searchPlaceholder: "İsim veya telefon ara...",
  views: {
    table: "Liste",
    grid: "Kartlar",
  },
  activeOnly: "Sadece Aktif",
  allLicenses: "Tüm Ehliyetler",
  licenseSuffix: (value: string) => `${value} Sınıfı`,
  reset: "Sıfırla",
  scoreRange: "Puan Aralığı",
  minScore: "Min",
  maxScore: "Max",
} as const;

export const driverGridText = {
  status: {
    active: "Aktif",
    inactive: "Pasif",
  },
  licenseSuffix: (value: string) => `${value} Sınıfı Ehliyet`,
  actions: {
    aiAnalysis: "AI Analiz",
    edit: "Düzenle",
    delete: "Sil",
  },
} as const;

export const driverTableText = {
  columns: {
    driver: "Şoför",
    contact: "İletişim",
    score: "Puan",
    status: "Durum",
    actions: "İşlemler",
  },
  status: {
    active: "Aktif",
    inactive: "Pasif",
  },
  licenseSuffix: (value: string) => `${value} Sınıfı`,
  actions: {
    aiAnalysis: "AI Analiz",
    score: "Puanla",
    edit: "Düzenle",
    delete: "Sil",
  },
} as const;

export const driverPerformanceText = {
  title: "Şoför Karnesi",
  subtitle: (name: string) => `${name} • AI Performans Analizi`,
  loading: "Analiz ediliyor...",
  errorFallback: "Performans verileri alınamadı.",
  totalScore: "Genel Performans Skoru",
  trends: {
    increasing: "Yükselişte",
    decreasing: "Düşüşte",
    stable: "Stabil",
  },
  cards: {
    safety: "Güvenli Sürüş",
    eco: "Ekonomik Sürüş",
    compliance: "Kurallara Uyum",
  },
  stats: {
    trips: "Analiz Edilen Sefer",
    distance: "Toplam KM",
  },
  tabs: {
    performance: "Performans",
    breakdown: "Skor Detayı",
    routes: "Güzergah Profili",
  },
} as const;

export const driverModalText = {
  title: {
    edit: "Şoförü Düzenle",
    create: "Yeni Şoför Ekle",
  },
  description: "Şoför bilgilerini girin.",
  fields: {
    fullName: "Ad Soyad *",
    phone: "Telefon",
    licenseClass: "Ehliyet Sınıfı",
    startDate: "İşe Başlama",
    manualScore: "Manuel Puan",
    notes: "Notlar",
    active: "Şoför Aktif",
    activeDescription: "Pasif şoförler seferlere atanamaz.",
  },
  placeholders: {
    fullName: "Örn: Ahmet Yılmaz",
    phone: "0532 123 45 67",
    notes: "Şoför hakkında notlar...",
  },
  validation: {
    nameMin: "İsim en az 3 karakter olmalı.",
    nameMax: "İsim en fazla 100 karakter olabilir.",
    phone: "Geçerli bir telefon numarası girin.",
    licenseClass: "Ehliyet sınıfı seçin.",
    notesMax: "Notlar en fazla 500 karakter olabilir.",
  },
  scoreRange: {
    low: "0.1 Düşük",
    high: "2.0 Mükemmel",
  },
  actions: {
    cancel: "İptal",
    update: "Güncelle",
    save: "Kaydet",
  },
} as const;

export const driverScoreText = {
  title: "Puan Güncelle",
  sections: {
    current: "Mevcut Durum",
    manual: "Manuel Değerlendirme",
    estimated: "Tahmini Hibrit Puan",
  },
  labels: {
    currentManual: (value: number) => `Manuel: ${value.toFixed(1)}`,
    hybridFormula: "* Hibrit = %60 Performans + %40 Manuel Değerlendirme",
  },
  scoreBands: {
    risk: "0.1 Riskli",
    neutral: "1.0 Nötr",
    excellent: "2.0 Mükemmel",
  },
  levels: {
    excellent: "Mükemmel",
    good: "İyi",
    medium: "Orta",
    low: "Düşük",
    veryLow: "Çok Düşük",
  },
  actions: {
    cancel: "İptal",
    update: "Güncelle",
  },
} as const;
