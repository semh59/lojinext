export const tripPageText = {
  heading: "Sefer Yönetimi",
  description:
    "Sistemdeki tüm sevkiyatları ve anomali analizlerini buradan yönetebilirsiniz.",
} as const;

export const tripHeaderText = {
  title: "Sefer Yönetimi",
  subtitlePrimary: "Operasyonel Kontrol",
  subtitleSecondary: "Lojistik Takip Sistemi",
  showAnalytics: "Yakıt Performansı",
  hideAnalytics: "Paneli Kapat",
  createTrip: "Yeni Sefer",
  createTripAria: "Yeni Sefer Oluştur",
} as const;

export const tripStatsText = {
  heading: "Sefer Performans Göstergeleri",
  totalTripsLabel: (isCompletedView: boolean) =>
    `${isCompletedView ? "Toplam Tamamlanan" : "Toplam"} Sefer`,
  cancelledLabel: "İptal Edilen",
  roadCharacter: "Yol Karakteri",
  highwayShare: (value: number) => `%${value} Otoyol`,
  totalAscent: "Toplam Tırmanış",
  totalWeight: "Toplam Tonaj",
  weightUnit: "Ton",
} as const;

export const tripModuleText = {
  approvalQueueBanner: (count: number) =>
    `${count} sefer Telegram onayı bekliyor`,
  bulkApprove: "Seçilileri Onayla",
  lastUpdated: (sec: number) => `son güncelleme: ${sec} sn önce`,
  loadErrorTitle: "Veri Yüklenemedi",
  loadErrorForbidden:
    "Seferleri görüntüleme yetkiniz bulunmuyor. Rol izinlerini kontrol edin.",
  loadErrorGeneric: "Lütfen internet bağlantınızı kontrol edip tekrar deneyin.",
  retry: "Yeniden Dene",
  createSuccess: "Yeni sefer başarıyla kaydedildi.",
  createErrorFallback: "Sefer kaydedilemedi.",
  updateSuccess: "Sefer bilgileri güncellendi.",
  updateConflict:
    "Bu kayıt başka biri tarafından güncellenmiş. Lütfen sayfayı yenileyip tekrar deneyin.",
  updateErrorFallback: "Güncelleme sırasında bir hata oluştu.",
  deleteSuccess: "Sefer silindi.",
  deleteErrorFallback: "Silme işlemi başarısız oldu.",
  returnSuccess: "Dönüş seferi başarıyla oluşturuldu.",
  returnErrorFallback: "Dönüş seferi oluşturulamadı.",
  bulkStatusSuccess: (count: number) => `${count} sefer güncellendi.`,
  bulkStatusError: (count: number) => `${count} sefer güncellenemedi.`,
  bulkCancelSuccess: (count: number) => `${count} sefer iptal edildi.`,
  bulkCancelError: (count: number) => `${count} sefer iptal edilemedi.`,
  bulkDeleteSuccess: (count: number) => `${count} sefer başarıyla silindi.`,
  bulkDeleteError: (count: number) => `${count} sefer silinemedi.`,
  bulkDeleteFallback: "Toplu silme sırasında bir hata oluştu.",
  deleteConfirm: "Bu seferi silmek istediğinize emin misiniz?",
  returnConfirm:
    "Bu sefer için otomatik dönüş seferi oluşturulacaktır. Onaylıyor musunuz?",
  bulkDeleteConfirm: (count: number) =>
    `${count} seferi silmek istediğinize emin misiniz?`,
  statusTransitionMissing: (status: string) =>
    `'${status}' durumundan geçiş yok.`,
  statusPrompt: (allowedStatuses: string) => `Yeni durum (${allowedStatuses}):`,
  invalidStatus: "Geçersiz durum seçildi.",
  cancellationReasonPrompt: "İptal nedeni girin (en az 5 karakter):",
  cancellationReasonInvalid: "İptal nedeni en az 5 karakter olmalıdır.",
  exportLoading: "Excel dosyası hazırlanıyor, lütfen bekleyin...",
  exportSuccess: "Excel dosyası başarıyla indirildi.",
  exportError: "Dışa aktarma sırasında hata oluştu.",
  exportFileNamePrefix: "seferler_export",
  templateFileName: "sefer_yukleme_sablonu.xlsx",
  templateSuccess: "Şablon indirildi.",
  templateError: "Şablon indirilemedi.",
  importSuccess: (count: number) => `${count} sefer başarıyla yüklendi.`,
  importError: "Dosya yüklenemedi.",
  totalRecords: (count: number) =>
    `Toplam ${count.toLocaleString("tr-TR")} Kayıt`,
  previousPage: "Önceki",
  nextPage: "Sonraki",
} as const;

export const tripFilterText = {
  todayFilter: "Bugün",
  searchPlaceholder: "Sefer numarası, araç veya sürücü ara...",
  openFilters: "Filtrele",
  advancedFiltersTitle: "Gelişmiş Filtreler",
  advancedFiltersDescription: "Kayıtları daraltın",
  statusLabel: "Sefer Durumu",
  dateRangeLabel: "Tarih Aralığı",
  savedFiltersLabel: "Kayıtlı Filtrelerim",
  reset: "Sıfırla",
  apply: "Uygula",
  saveCurrentFilter: "Mevcut Filtreyi Kaydet",
  saveDialogTitle: "Filtreyi Kaydet",
  filterNameLabel: "Filtre Adı",
  filterNamePlaceholder: "Örn: Aktif Seferler",
  cancel: "İptal",
  save: "Kaydet",
  saveNameRequired: "Lütfen filtre için bir isim girin.",
  saveSuccess: "Filtre kaydedildi.",
  saveError: "Filtre kaydedilemedi.",
  deleteSuccess: "Filtre silindi.",
  deleteError: "Filtre silinemedi.",
  resetSuccess: "Filtreler sıfırlandı.",
  tabs: {
    all: "Tümü",
    planned: "Planlandı",
    completed: "Tamamlandı",
    canceled: "İptal",
  },
} as const;

export const tripTableText = {
  emptyTitle: "Henüz Sefer Yok",
  emptyDescription: "Sistemde kayıtlı bir aktif operasyonel sefer bulunmuyor.",
  filteredEmptyTitle: "Sonuç Bulunamadı",
  filteredEmptyDescription:
    "Seçili filtrelere uygun kayıt bulamadık. Lütfen kriterleri güncelleyin.",
  clearFilters: "Tüm Filtreleri Temizle",
  fallbackTripNumber: (id?: number) => `Sefer #${id ?? "-"}`,
  unknownValue: "Belirsiz",
  noTrailer: "Dorse Yok",
  vehicleLabel: "Operasyonel Araç",
  driverLabel: "Sorumlu Sürücü",
  trailerFallback: (id: number) => `Dorse #${id}`,
  updateStatus: "Durum Güncelle",
  createReturn: "Dönüş Seferi",
  costAnalysis: "Maliyet Analizi",
  deleteTrip: "Seferi Sil",
  openMenu: "Sefer İşlemleri",
  selectedTrips: "Seçili Sefer",
  bosSefer: "Boş Sefer",
  roundTrip: "Dönüş",
  versionLabel: (v: number) => `v${v}`,
  actualConsumption: "Gerçek Tüketim",
  delayed: (min: number) => `+${min} dk gecikmeli`,
  early: (min: number) => `-${min} dk erken`,
  odometerWarning: (diff: number) =>
    `Km farkı: ${diff > 0 ? "+" : ""}${diff} km`,
  rejectionReason: "Red Nedeni",
} as const;

export const tripAnalyticsText = {
  insufficientTitle: "Yetersiz Analiz Verisi",
  insufficientDescription:
    "Derinlemesine karşılaştırma için henüz yeterli veri setine sahip değiliz. En az 3 adet tamamlanmış ve tahminlenmiş sefer gereklidir.",
  kpis: {
    mae: { label: "MAE", description: "Ortalama Mutlak Hata" },
    rmse: { label: "RMSE", description: "Kök Ortalama Kare Hata" },
    compared: { label: "Eşleşen", description: "Kıyaslanan Veri Seti" },
    highDeviation: {
      label: "Yüksek Sapma",
      description: "%15 Eşik Değer Üstü",
    },
  },
  trend: {
    title: "Tahmin Trendi",
    description: "Gerçek vs Tahmin Karşılaştırması",
    predicted: "Tahmin",
    actual: "Gerçek",
  },
  distribution: {
    title: "Sapma Dağılımı",
    description: "Hata Sınıflarının Frekansı",
    good: "İyi",
    warning: "Kabul",
    error: "Sapma",
  },
  outliers: {
    title: "En Yüksek Sapmalar (Outlier)",
    description: "Kayıp kaçağın en yoğun olduğu seferler",
    missingPlate: "Plaka Yok",
    deviationLabel: "Sapma",
  },
} as const;

export const tripBulkActionText = {
  selectedTrips: "Seçili Sefer",
  updateStatus: "Durum Güncelle",
  cancel: "İptal Et",
  bulkDelete: "Toplu Sil",
} as const;

export const tripBulkStatusModalText = {
  title: "Toplu Durum Güncelle",
  selectedTrips: (count: number) => `${count} Sefer Seçildi`,
  description:
    "Seçili seferleri toplu olarak planlandı veya tamamlandı durumuna alın.",
  planned: "Planlandı",
  completed: "Tamamlandı",
  cancelHint:
    "Toplu iptal ayrı akıştan yapılır. İptal işlemi için “İptal Et” aksiyonunu kullanın.",
  cancel: "Vazgeç",
  confirm: "Güncelle",
} as const;

export const tripBulkCancelModalText = {
  title: "Toplu Sefer İptali",
  summary: (count: number) => `${count} Sefer İptal Edilecek`,
  description:
    "Bu işlem geri alınamaz, ancak manuel olarak tekrar planlama yapılabilir.",
  reasonLabel: "İptal Nedeni (Zorunlu)",
  reasonPlaceholder: "Örn: Araç arızası, müşteri iptali...",
  reasonHint: "Neden paylaşmadan iptal edilemez.",
  cancel: "Vazgeç",
  confirm: "İptal Et",
} as const;

export const tripFormModalText = {
  validation: {
    dateRequired: "Tarih gereklidir.",
    invalidTime: "Geçersiz saat formatı (HH:mm).",
    tripNumberMax: "En fazla 50 karakter girilebilir.",
    vehicleRequired: "Araç seçimi gereklidir.",
    driverRequired: "Sürücü seçimi gereklidir.",
    routeRequired: "Güzergâh seçimi gereklidir.",
    departureRequired: "Çıkış yeri gereklidir.",
    arrivalRequired: "Varış yeri gereklidir.",
    distancePositive: "Mesafe 0’dan büyük olmalıdır.",
    weightNonNegative: "Ağırlık alanları negatif olamaz.",
  },
  titles: {
    readOnly: "Sefer Detayları",
    edit: "Seferi Güncelle",
    create: "Yeni Sefer Girişi",
  },
  tabs: {
    details: "Sefer Detayları",
    timeline: "İşlem Geçmişi",
  },
  statusLabel: "Operasyonel Statü",
  actions: {
    close: "Pencereyi Kapat",
    cancel: "Vazgeç",
    submitting: "İşleniyor...",
    saveUpdate: "Güncellemeyi Kaydet",
    approveTrip: "Seferi Onayla",
  },
  formError: "Lütfen formdaki hataları kontrol edin.",
} as const;

export const tripDateTimeSectionText = {
  heading: "Zamanlama İndeksi",
  dateLabel: "Operasyon Tarihi",
  timeLabel: "Çıkış Saati",
  referenceLabel: "Sefer / İş Referansı",
  referencePlaceholder: "Örn: SEF-2026-001",
} as const;

export const tripRouteSelectorText = {
  heading: "Güzergâh Planlama",
  emptyOption: "Lütfen bir güzergâh seçin...",
  inactiveTag: "(PASİF)",
  requiredErrorFallback: "Güzergâh seçimi zorunludur.",
  inactiveWarning:
    "Dikkat: Seçilen güzergâh sistemde pasif durumdadır. Lütfen yönetici ile iletişime geçin.",
  distanceUnit: "KM",
} as const;

export const tripStaffVehicleSectionText = {
  heading: "Varlık ve Personel Ataması",
  vehicleLabel: "Operasyonel Araç",
  vehiclePlaceholder: "Araç seçiniz...",
  trailerLabel: "Dorse (Opsiyonel)",
  trailerPlaceholder: "Dorse yok",
  driverLabel: "Sorumlu Sürücü",
  driverPlaceholder: "Sürücü atayınız...",
} as const;

export const tripLoadManagementSectionText = {
  heading: "Kargo ve Yük Parametreleri",
  emptyWeightLabel: "Boş Kantar (KG)",
  loadedWeightLabel: "Dolu Kantar (KG)",
  summaryTitle: "Net Taşıma Kapasitesi",
  summarySubtitle: "Operasyonel yük hesaplaması",
  unit: "KG",
} as const;

export const tripTelemetrySectionText = {
  heading: "Güzergâh ve Telemetri Özeti",
  departureLabel: "Çıkış",
  arrivalLabel: "Varış",
  distanceUnit: "KM",
  distanceErrorTitle: "Kritik Mesafe Hatası",
  emptyTitle: "Güzergâh Verisi Bekleniyor",
  emptyDescription:
    "Telemetri analizi için lütfen üst menüden bir güzergâh planlayın.",
} as const;

export const tripRoundTripSelectorText = {
  none: "Tek Yön",
  empty: "Boş Dönüş",
  loaded: "Dolu Dönüş",
} as const;

export const tripRoundTripSectionText = {
  heading: "Bağlı Dönüş Seferi (Otomatik)",
  tripNumberLabel: "Dönüş Seferi ID/No",
  tripNumberPlaceholder: "Sistem atayacak",
  returnLoadLabel: "Dönüş Kantar Yükü (KG)",
  returnLoadPlaceholder: "0",
} as const;

export const tripListText = {
  emptyTitle: "Aktif Sefer Yok",
  emptyDescription: "Planlanan bir sefer bulunmuyor.",
  missingPlate: "Plaka yok",
  vehicleLabel: "Araç",
  missingDriver: "Şoför yok",
  driverLabel: "Sürücü",
  unknownStatus: "Belirsiz",
} as const;

export const tripTimelineText = {
  eventLabels: {
    CREATE: "Oluşturma",
    UPDATE: "Güncelleme",
    STATUS_CHANGE: "Durum Geçişi",
    PREDICTION_REFRESH: "Tahmin Yenileme",
    RECONCILIATION: "Uzlaştırma",
    DELETE: "Silme",
  },
  empty: "Henüz operasyon kaydı bulunmuyor.",
  technicalDetails: "Teknik Detaylar",
  predictionInfo: "Tahmin Bilgisi",
  fieldChanges: "Alan Değişimleri",
  model: "Model",
  version: "Versiyon",
  confidence: "Güven",
  fallback: "Fallback",
  yes: "Evet",
  no: "Hayır",
} as const;
