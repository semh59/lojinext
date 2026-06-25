export const trailerModuleText = {
  notifications: {
    deleteSuccess: "Dorse başarıyla silindi.",
    importSuccess: "Dorseler başarıyla içe aktarıldı.",
    importError: "İçe aktarma sırasında bir hata oluştu.",
    updateSuccess: "Dorse başarıyla güncellendi.",
    createSuccess: "Yeni dorse başarıyla eklendi.",
    saveFallback: "Kayıt sırasında bir hata oluştu.",
  },
  pagination: {
    previous: "Önceki",
    next: "Sonraki",
  },
} as const;

export const trailerHeaderText = {
  title: "Dorse Yönetimi",
  description:
    "Filo dorselerini izleyin, teknik detayları ve durumları yönetin.",
  addButton: "Yeni Dorse Ekle",
} as const;

export const trailerFilterText = {
  searchPlaceholder: "Dorse, plaka veya marka ara...",
  titles: {
    gridView: "Kart Görünümü",
    listView: "Liste Görünümü",
    activeOnly: "Aktif Dorseler",
    advancedFilters: "Detaylı Filtre",
  },
  fields: {
    brand: "Marka",
    model: "Model",
    minYear: "Minimum Yıl",
    maxYear: "Maksimum Yıl",
  },
  placeholders: {
    brand: "Örn: Tırsan",
    model: "Örn: Frigo",
    minYear: "2015",
    maxYear: "2024",
  },
  reset: "Temizle",
  apply: "Uygula",
} as const;

export const trailerTableText = {
  emptyTitle: "Henüz Dorse Eklenmemiş",
  emptyDescription:
    "Filo yönetimine başlamak için sağ üstteki butondan yeni bir dorse ekleyerek operasyonlarınızı başlatın.",
  title: "Filo Dorseleri",
  totalCount: (count: number) => `Toplam: ${count} Dorse`,
  columns: {
    plateAndBrand: "Plaka & Marka",
    typeAndYear: "Tip & Yıl",
    technical: "Teknik Parametreler",
    status: "Durum",
    actions: "İşlemler",
  },
  status: {
    active: "AKTİF",
    inactive: "PASİF",
  },
  labels: {
    unknownBrand: "Bilinmiyor",
    modelSuffix: "Model",
    tireCount: "Lastik",
    modelYear: "Model Yılı",
    emptyWeight: "Boş Ağırlık",
    tireCountCard: "Lastik Sayısı",
    pieceSuffix: "Adet",
  },
  actions: {
    detail: "Detay",
    details: "Detaylar",
    edit: "Düzenle",
    delete: "Sil",
  },
} as const;

export const trailerDetailText = {
  tabs: {
    general: "Genel Bakış",
    technical: "Teknik Özellikler",
    maintenance: "Bakım Geçmişi",
  },
  status: {
    active: "AKTİF",
    inactive: "PASİF",
  },
  sections: {
    basic: "Temel Bilgiler",
    operational: "Operasyonel Durum",
    weight: "Ağırlık & Kapasite",
    physical: "Fiziksel Parametreler",
  },
  fields: {
    plate: "Plaka",
    brandModel: "Marka / Model",
    modelYear: "Model Yılı",
    type: "Tip",
    notes: "Notlar",
    unspecified: "Belirtilmemiş",
    emptyWeight: "Boş Ağırlık",
    tireCount: "Lastik Sayısı",
    rollingResistance: "Lastik Direnci",
    dragContribution: "Hava Direnci Katkısı",
    close: "Kapat",
  },
  maintenance: {
    unavailableTitle: "Bakım kayıtları şu anda görüntülenemiyor.",
    unavailableDescription:
      "Gerçek bakım geçmişi sisteme düştüğünde burada gösterilecek.",
  },
} as const;

export const trailerDeleteText = {
  title: "Dorse Silinsin mi?",
  description: (plate: string) =>
    `${plate} plakalı dorseyi silmek istediğinize emin misiniz? Bu işlem geri alınamaz.`,
  confirm: "Dorseyi Kalıcı Olarak Sil",
  cancel: "Vazgeç",
} as const;

export const trailerModalText = {
  title: {
    edit: "Dorse Düzenle",
    create: "Yeni Dorse Ekle",
  },
  subtitle: {
    edit: (id: number | undefined, plate: string | undefined) =>
      `ID: ${id ?? "-"} | ${plate ?? "-"}`,
    create: "Lojistik altyapı kaydı",
  },
  sections: {
    basic: "Temel Bilgiler",
    technical: "Fizik & Teknik Parametreler",
  },
  fields: {
    plate: "Plaka",
    brand: "Marka",
    type: "Tip",
    modelYear: "Model Yılı",
    inspectionDate: "Muayene Tarihi",
    emptyWeight: "Boş Ağırlık (kg)",
    payload: "Yük Kapasitesi (kg)",
    tireCount: "Lastik Sayısı",
    advancedCoefficients: "Gelişmiş Katsayılar (Physics Engine)",
    rollingResistance: "Lastik Direnci (Crr)",
    dragContribution: "Hava Direnci Katkısı",
    notes: "Notlar",
    active: "Aktif Kullanım Durumu",
    activeDescription: "Pasifleştirilen dorseler seferlerde seçilemez.",
  },
  placeholders: {
    plate: "34 ABC 123",
    brand: "Krone, Tırsan vb.",
    notes: "Bakım geçmişi, lastik durumu vb.",
  },
  options: {
    standard: "Standart",
    frigo: "Frigo",
    tented: "Tenteli",
    tipper: "Damperli",
    lowbed: "Lowbed",
  },
  actions: {
    cancel: "İptal",
    update: "Güncelle",
    save: "Kaydet",
  },
} as const;
