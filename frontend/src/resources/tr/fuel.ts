export const fuelPageText = {
  heading: "Yakıt Yönetimi",
  description:
    "Tüketim analizi, maliyet takibi ve yakıt verimliliğini yönetin.",
  notifications: {
    updateSuccessTitle: "Güncellendi",
    updateSuccessMessage: "Kayıt başarıyla güncellendi.",
    createSuccessTitle: "Eklendi",
    createSuccessMessage: "Yeni yakıt kaydı eklendi.",
    actionErrorTitle: "Hata",
    actionErrorMessage: "İşlem başarısız.",
    deleteConfirm: "Bu kaydı silmek istediğinize emin misiniz?",
    deleteSuccessTitle: "Başarılı",
    deleteSuccessMessage: "Kayıt silindi.",
    deleteErrorFallback: "Silinemedi.",
    exportSuccessTitle: "Başarılı",
    exportSuccessMessage: "Excel indirildi.",
    exportErrorMessage: "Dışa aktarma başarısız.",
    templateErrorMessage: "Şablon indirilemedi.",
    importSuccessTitle: "Başarılı",
    importSuccessMessage: "İçe aktarıldı.",
    importErrorMessage: "İçe aktarma başarısız.",
  },
  exportFileNamePrefix: "yakit_takip",
  templateFileName: "yakit_import_sablonu.xlsx",
} as const;

export const fuelHeaderText = {
  addRecord: "Yeni Kayıt Ekle",
} as const;

export const fuelFilterText = {
  vehiclePlaceholder: "Araç seçiniz...",
  apply: "Uygula",
  reset: "Temizle",
} as const;

export const fuelStatsText = {
  unavailable:
    "Yakıt istatistikleri şu anda alınamıyor. Gerçek veri gelmeden özet kartları gösterilmiyor.",
  totalConsumption: "Toplam Tüketim",
  totalCost: "Toplam Maliyet",
  averageConsumption: "Ortalama Tüketim",
  averagePrice: "Ortalama Fiyat",
  totalDistance: "Toplam Mesafe",
  fuelAnomalies: "Yakıt Anomalisi",
  fuelAnomaliesSubtitle: "son 30 günde tespit edildi",
  verifiedDataHint: "yalnız doğrulanmış dönem verisi gösterilir",
} as const;

export const fuelTableText = {
  emptyTitle: "Kayıt Bulunamadı",
  emptyDescription: "Belirlediğiniz filtrelere uygun yakıt kaydı bulunmuyor.",
  headers: {
    dateTime: "Tarih & Saat",
    plate: "Araç Plakası",
    stationReceipt: "İstasyon / Fiş No",
    liters: "Miktar (Litre)",
    unitPrice: "Litre Fiyatı",
    totalAmount: "Toplam Tutar",
    actions: "İşlem",
  },
  defaults: {
    time: "12:00",
    station: "Bilinmiyor",
    receipt: "-",
  },
  receiptLabel: "Fiş",
  actions: {
    edit: "Düzenle",
    delete: "Sil",
  },
} as const;

export const fuelPaginationText = {
  totalRecords: (count: number) =>
    `Toplam ${count.toLocaleString("tr-TR")} kayıt`,
  firstPage: "İlk sayfa",
  previous: "Önceki",
  next: "Sonraki",
  lastPage: "Son sayfa",
  pageSummary: (currentPage: number, totalPages: number) =>
    `Sayfa ${currentPage} / ${totalPages}`,
} as const;

export const fuelComparisonText = {
  unavailableTitle: "Yetersiz Veri",
  unavailableDescription:
    "Karşılaştırma için hem tahmin hem gerçek tüketim verisi olan en az 1 sefer gereklidir.",
  averageErrorLabel: "Ortalama Hata",
  performanceTitle: "Model Performansı",
  maeUnit: "L/100km (MAE)",
  rmseValue: (value: number) => `RMSE değeri: ${value.toFixed(2)} L/100km`,
  accuracyTitle: "Doğruluk Dağılımı",
  accuracy: {
    good: "%5 altı (iyi)",
    warning: "%5-%15 (kabul)",
    error: "%15 üstü (sapma)",
    tripCount: (count: number) => `${count} sefer`,
  },
  analysisLabel: "Tahmin Analizi",
  trendTitle: "Tahmin vs Gerçek Trend",
  legend: {
    predicted: "Tahmin",
    actual: "Gerçek",
  },
  tooltip: {
    ratio: "Oran",
  },
  summary: (totalCompared: number) =>
    `Bu grafik son ${totalCompared} seferden alınan verilerle oluşturulmuştur.`,
  summaryHint: "MAE değeri sıfıra yaklaştıkça model doğruluğu artar.",
} as const;

export const fuelModalText = {
  editTitle: "Yakıt Kaydını Düzenle",
  createTitle: "Yeni Yakıt Kaydı",
  description: "Araç yakıt alım bilgilerini giriniz.",
  labels: {
    date: "Tarih",
    vehicle: "Araç",
    station: "İstasyon",
    liters: "Litre",
    unitPrice: "Birim Fiyat (TL)",
    total: "Toplam (Otomatik)",
    odometer: "KM Sayaç",
    receiptNumber: "Fiş Numarası",
    tankStatus: "Depo Durumu",
  },
  placeholders: {
    vehicle: "Seçiniz",
    station: "Örn: Shell Maslak",
    receiptNumber: "Örn: FIS-123",
  },
  tankStatusOptions: {
    full: "Tam Doldu",
    partial: "Kısmi Alım",
    unknown: "Bilinmiyor",
  },
  actions: {
    cancel: "İptal",
    save: "Kaydet",
  },
  validation: {
    dateRequired: "Tarih zorunludur",
    vehicleRequired: "Araç seçiniz",
    stationRequired: "İstasyon zorunludur",
    litersPositive: "Litre 0'dan büyük olmalı",
    unitPricePositive: "Birim fiyat 0'dan büyük olmalı",
    totalPositive: "Toplam tutar 0 veya daha fazla olmalı",
    odometerPositive: "KM sayacı 0 veya daha fazla olmalı",
  },
  enums: {
    partial: "Kısmi",
    full: "Doldu",
    pending: "Bekliyor",
    approved: "Onaylandı",
    rejected: "Reddedildi",
  },
} as const;
