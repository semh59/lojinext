export const vehicleModuleText = {
  notifications: {
    update: {
      title: "Güncellendi",
      description: "Araç bilgileri başarıyla güncellendi.",
    },
    create: {
      title: "Eklendi",
      description: "Yeni araç başarıyla eklendi.",
    },
    actionSuccess: {
      title: "İşlem Başarılı",
      description: "İşlem tamamlandı.",
    },
    errorTitle: "Hata",
    saveFallback: "İşlem sırasında bir hata oluştu.",
    deleteFallback: "Araç silinemedi.",
    export: {
      successTitle: "Başarılı",
      successDescription: "Excel dosyası hazırlandı.",
      errorDescription: "Dışa aktarma başarısız.",
    },
    template: {
      successTitle: "Başarılı",
      successDescription: "Şablon indirildi.",
      errorDescription: "Şablon indirilemedi.",
    },
    import: {
      successTitle: "Başarılı",
      successDescription: "Araçlar başarıyla içe aktarıldı.",
      errorDescription: "İçe aktarma başarısız.",
    },
  },
  files: {
    exportPrefix: "araclar_export",
    templateName: "arac_yukleme_sablonu.xlsx",
  },
  pagination: {
    page: (currentPage: number, totalPages: number) =>
      `Sayfa ${currentPage} / ${totalPages}`,
  },
} as const;

export const vehicleHeaderText = {
  addButton: "Yeni Araç Ekle",
} as const;

export const vehicleFilterText = {
  searchPlaceholder: "Araç, plaka veya marka ara...",
  activeOnly: "Aktif Araçlar",
  advancedFilters: "Detaylı Filtre",
  fields: {
    brand: "Marka",
    model: "Model",
    minYear: "Minimum Yıl",
    maxYear: "Maksimum Yıl",
  },
  placeholders: {
    brand: "Örn: Mercedes",
    model: "Örn: Actros",
    minYear: "2015",
    maxYear: "2024",
  },
  reset: "Temizle",
  apply: "Uygula",
  skeleton: {
    columns: {
      vehicle: "Araç",
      plate: "Plaka",
      year: "Yıl",
      tank: "Tank",
      target: "Hedef",
      status: "Durum",
      actions: "İşlemler",
    },
  },
} as const;

export const vehicleTableText = {
  emptyTitle: "Henüz Araç Eklenmemiş",
  emptyDescription:
    "Filo yönetimine başlamak için sağ üstteki butondan yeni bir araç ekleyerek operasyonlarınızı başlatın.",
  title: "Filo Araçları",
  totalCount: (count: number) => `Toplam: ${count} Araç`,
  status: {
    active: "AKTİF",
    inactive: "PASİF",
  },
  labels: {
    modelYear: "Model Yılı",
    fuelCapacity: "Yakıt Kapasitesi",
    targetConsumption: "Hedef Tüketim (L/100km)",
  },
  actions: {
    insights: "İçgörüler",
    detail: "Detaylar",
    edit: "Düzenle",
    delete: "Sil",
  },
} as const;

export const vehicleDeleteText = {
  title: {
    soft: "Aracı Pasife Al",
    hard: "Kalıcı Olarak Sil",
  },
  description: {
    soft: (plate: string) =>
      `${plate} plakalı aracı pasif duruma getirmek üzeresiniz. Araç varsayılan listelerde görünmeyecek ancak verileri saklanacaktır.`,
    hard: (plate: string) =>
      `${plate} plakalı aracı tamamen silmek üzeresiniz. Bu işlem geri alınamaz ve tüm geçmiş veriler kaldırılır.`,
  },
  actions: {
    cancel: "İptal",
    softConfirm: "Pasife Al",
    hardConfirm: "Evet, Sil",
  },
} as const;

export const vehicleDetailText = {
  errors: {
    statsUnavailable: "Araç istatistikleri şu anda alınamıyor.",
    eventsUnavailable: "Olay geçmişi alınamıyor.",
  },
  status: {
    active: "Aktif",
    inactive: "Pasif",
  },
  stats: {
    totalTrips: "Toplam Sefer",
    totalDistance: "Toplam Kilometre",
    averageConsumption: "Ort. Tüketim",
    totalFuel: "Toplam Yakıt",
  },
  efficiency: {
    label: "Verimlilik Skoru",
    efficient: (pct: number) => `+%${pct.toFixed(1)} verimli`,
    inefficient: (pct: number) => `-%${pct.toFixed(1)} kayıp`,
    noData: "Veri yok",
    targetLabel: "Hedef Tüketim",
    actualLabel: "Gerçek Ortalama",
  },
  inspection: {
    label: "Muayene Tarihi",
    expiredBadge: "MUAYENESİ GEÇMİŞ",
    expiringSoonBadge: (days: number) => `${days} GÜN KALDI`,
    okBadge: "Muayene Geçerli",
  },
  aging: {
    label: (years: number) => `${years} Yaşında`,
    degradation: (pct: number) => `Yaşlanma Etkisi: -%${pct.toFixed(1)}`,
  },
  events: {
    title: "Olay Geçmişi",
    noEvents: "Henüz kayıtlı olay yok.",
    types: {
      CREATED: "Oluşturuldu",
      RE_ACTIVATED: "Yeniden Aktifleştirildi",
      STATUS_CHANGED: "Durum Değiştirildi",
      UPDATED: "Güncellendi",
    } as Record<string, string>,
    by: (who: string) => `· ${who}`,
  },
  sections: {
    basic: "Temel Bilgiler",
    physics: "Fizik Parametreleri",
    notes: "Notlar",
    events: "Olay Geçmişi",
  },
  fields: {
    productionYear: "Üretim Yılı",
    tankCapacity: "Tank Kapasitesi",
    targetConsumption: "Hedef Tüketim",
    maxPayload: "Maks Yük",
    emptyWeight: "Boş Ağırlık",
    dragCoefficient: "Hava Direnci (Cd)",
    frontalArea: "Ön Kesit",
    engineEfficiency: "Motor Verimi",
    rollingResistance: "Lastik Direnci",
    inspectionDate: "Muayene Tarihi",
  },
} as const;

export const vehicleCardText = {
  inspection: {
    expired: "MUAYENESİ GEÇMİŞ",
    expiringSoon: (days: number) => `MUAYENE: ${days}G`,
  },
  aging: {
    badge: (years: number) => `${years} YAŞ`,
    old: "ESKİ ARAÇ",
  },
} as const;

export const vehicleModalText = {
  title: {
    edit: "Aracı Düzenle",
    create: "Yeni Araç Ekle",
  },
  description: {
    edit: "Araç bilgilerini güncelleyin",
    create: "Filoya yeni araç ekleyin",
  },
  fields: {
    plate: "Plaka *",
    brand: "Marka *",
    model: "Model",
    year: "Yıl",
    tankCapacity: "Tank Kapasitesi",
    targetConsumption: "Hedef Tüketim",
    notes: "Notlar",
    active: "Araç Aktif",
    activeDescription: "Pasif araçlar listede gri görünür.",
    physics: "Fizik Parametreleri",
    emptyWeight: "Boş Ağırlık",
    dragCoefficient: "Hava Direnci (Cd)",
    frontalArea: "Ön Kesit",
    engineEfficiency: "Motor Verimi",
    rollingResistance: "Lastik Direnci",
    maxPayload: "Maks Yük Kapasitesi",
  },
  placeholders: {
    plate: "34 ABC 123",
    brand: "Mercedes",
    model: "Actros",
    notes: "Araç hakkında ek bilgiler...",
  },
  validation: {
    plateMin: "Plaka en az 3 karakter olmalı.",
    brandMin: "Marka en az 2 karakter olmalı.",
  },
  actions: {
    cancel: "İptal",
    update: "Güncelle",
    create: "Ekle",
  },
} as const;
