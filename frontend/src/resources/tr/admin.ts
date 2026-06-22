export const adminOverviewText = {
  heading: "Sistem Genel Bakış",
  description:
    "Yönetim paneli yalnız gerçek servis ve rapor verilerini gösterir.",
  cards: {
    totalTrips: "Toplam Sefer",
    activeVehicles: "Aktif Araç",
    systemStatus: "Sistem Durumu",
    database: "Veritabanı",
  },
  consumptionTrend: {
    title: "Yakıt Tüketim Trendi",
    description: "Son raporlanan dönemlerden gerçek tüketim toplamları.",
    empty: "Henüz gösterilecek tüketim trend verisi bulunmuyor.",
  },
  operationalHealth: {
    title: "Operasyonel Sağlık Özeti",
    description:
      "Yedekleme ve devre kesici durumu canlı sağlık uçlarından okunur.",
    circuitBreakers: "Devre Kesiciler",
    lastBackup: "Son Yedekleme",
    noBackup: "Henüz yedek bulunmuyor",
  },
} as const;

export const adminMlText = {
  heading: "ML Modelleri ve Eğitim",
  description:
    "Eğitim kuyruğunu izleyin ve eğitimi yalnız gerçek araç kayıtları üzerinden başlatın.",
  vehicleNotFound: "Araç bulunamadı",
  startTraining: "Eğitimi Başlat",
  notifications: {
    trainingStarted: "Model eğitimi başlatıldı",
    trainingStartFailed: "Eğitim başlatılamadı",
    selectVehicle: "Eğitim başlatmak için araç seçin",
  },
  cards: {
    totalTasks: "Toplam Görev",
    runningTasks: "Çalışan Görev",
    latestRmse: "Son RMSE",
    completedTasks: (count: number) => `${count} tamamlanmış görev`,
  },
  table: {
    title: "Eğitim Kuyruğu",
    vehicleId: "Araç ID",
    status: "Durum",
    algorithmRmse: "Algoritma / RMSE",
    duration: "Eğitim Süresi",
    detail: "Detay",
    createdAt: "Tarih",
    vehiclePrefix: "Araç",
    secondsShort: "sn",
    empty: "Kuyrukta eğitim görevi yok.",
  },
} as const;

export const adminHealthText = {
  heading: "Sistem Sağlığı",
  description:
    "Servis durumlarını, veritabanı performansını ve devre kesicileri izleyin.",
  refresh: "Yenile",
  backup: "Manuel Yedek Al",
  notifications: {
    loadFailed: "Sistem sağlığı verileri yüklenemedi",
    resetSuccess: (serviceName: string) =>
      `${serviceName} devre kesici sıfırlandı`,
    resetFailed: "Sıfırlama başarısız",
    backupStarted: "Veritabanı yedekleme işlemi başlatıldı",
    backupFailed: "Yedekleme başlatılamadı",
  },
  cards: {
    overallStatus: "Genel Durum",
    database: "Veritabanı",
    cache: "Redis/Cache",
  },
  circuitBreakers: {
    title: "Servis Devre Kesiciler",
    serviceName: "Servis Adı",
    status: "Durum",
    failureCount: "Hata Sayısı",
    detail: "Detay",
    actions: "İşlemler",
    reset: "Sıfırla",
    empty: "Devre kesici bilgisi bulunamadı",
  },
} as const;

export const adminConfigurationText = {
  heading: "Konfigürasyon Yönetimi",
  description:
    "Platform davranışlarını, ML parametrelerini ve sistem sınırlarını buradan yönetin.",
  loading: "Sistem ayarları yükleniyor",
  groupSuffix: "ayarları",
  reloadRequired: "Yeniden yükleme gerekli",
  valuePlaceholder: "Değer giriniz...",
  actions: {
    save: "Kaydet",
  },
  notifications: {
    loadFailedTitle: "Hata",
    loadFailedMessage: "Konfigürasyonlar yüklenemedi.",
    saveSuccessTitle: "Başarılı",
    saveSuccessMessage: "Ayar başarıyla kaydedildi.",
    saveFailedTitle: "Hata",
    saveFailedFallback: "Kaydetme başarısız.",
  },
} as const;

export const adminUsersText = {
  heading: "Kullanıcılar ve Roller",
  description:
    "Sistem erişim yetkilerini, kullanıcı rollerini ve aktif oturumları yönetin.",
  addUser: "Yeni Kullanıcı",
  loading: "Kullanıcı listesi yükleniyor",
  headers: {
    identity: "E-Posta / Kimlik",
    fullName: "Ad Soyad",
    role: "Rol",
    status: "Durum",
    lastLogin: "Son Giriş",
  },
  userId: (id: number) => `ID: #${id.toString().slice(-4)}`,
  statuses: {
    active: "Aktif",
    passive: "Pasif",
  },
  actions: {
    edit: "Düzenle",
  },
  unassignedRole: "Atanmamış",
  empty: "Kayıtlı kullanıcı bulunamadı",
} as const;

export const adminMaintenanceText = {
  heading: "Bakım ve Onarım Merkezi",
  description: "Araçların yaklaşan ve gecikmiş bakım görevlerini yönetin.",
  sectionTitle: "Acil ve Yaklaşan Bakımlar",
  loading: "Bakım uyarıları yükleniyor",
  headers: {
    vehicle: "Araç ID",
    maintenanceType: "Bakım Tipi",
    plannedDateOrKm: "Planlanan Tarih / KM",
    status: "Durum",
    actions: "İşlemler",
  },
  vehiclePrefix: "Araç",
  unknownStatus: "Bilinmiyor",
  completeAction: "Tamamlandı",
  empty: "Acil bakım uyarısı bulunmamaktadır",
  statusLabels: {
    overdue: "Gecikmiş",
    upcoming: "Yaklaşıyor",
    default: "Planlandı",
  },
  notifications: {
    loadFailedTitle: "Hata",
    loadFailedMessage: "Bakım uyarıları yüklenemedi",
    completeSuccessTitle: "Başarılı",
    completeSuccessMessage: "Bakım tamamlandı olarak işaretlendi",
    actionFailedTitle: "Hata",
    actionFailedFallback: "İşlem başarısız",
  },
} as const;

export const adminDataManagementText = {
  heading: "Veri İçe Aktarım ve Rollback",
  description:
    "Geçmiş Excel/CSV aktarımlarını görüntüleyin ve gerekirse geri alın.",
  sectionTitle: "Aktarım Geçmişi",
  loading: "Aktarım geçmişi yükleniyor",
  headers: {
    fileName: "Dosya Adı",
    type: "Tip",
    createdAt: "Tarih",
    status: "Durum",
    counts: "Kayıt (B/H/T)",
    actions: "İşlemler",
  },
  rollbackConfirm:
    "Bu aktarımı geri almak istediğinize emin misiniz? Bu işlem kalıcıdır ve ilgili verileri silecektir.",
  rollbackAction: "Geri Al",
  empty: "Aktarım geçmişi bulunamadı",
  statusLabels: {
    completed: "Tamamlandı",
    error: "Hata",
    rolledBack: "Geri Alındı",
    default: "İşleniyor",
  },
  notifications: {
    loadFailedTitle: "Hata",
    loadFailedMessage: "Aktarım geçmişi yüklenemedi",
    rollbackSuccessTitle: "Başarılı",
    rollbackSuccessMessage: "İşlem başarıyla geri alındı",
    rollbackFailedTitle: "Hata",
    rollbackFailedFallback: "Geri alma başarısız",
  },
} as const;

export const adminNotificationsText = {
  heading: "Bildirim Yönetimi",
  description: "Sistem içi bildirim ve e-posta kurallarını yapılandırın.",
  addRule: "Yeni Kural",
  sectionTitle: "Aktif Kurallar",
  loading: "Bildirim kuralları yükleniyor",
  headers: {
    eventType: "Olay Tipi",
    channels: "Kanallar",
    targetRole: "Hedef Rol ID",
    template: "Şablon",
    status: "Durum",
  },
  rolePrefix: "Rol",
  statuses: {
    active: "Aktif",
    passive: "Pasif",
  },
  empty: "Bildirim kuralı bulunamadı.",
  notifications: {
    loadFailedTitle: "Hata",
    loadFailedMessage: "Bildirim kuralları yüklenemedi",
  },
} as const;

export const adminLayoutText = {
  nav: {
    overview: "Genel Bakış",
    users: "Kullanıcılar",
    roles: "Roller",
    ml: "ML & Modeller",
    configuration: "Konfigürasyon",
    maintenance: "Bakım & Onarım",
    assignment: "Sefer Atama",
    accuracy: "Tahmin Doğruluğu",
    dataManagement: "Veri Yönetimi",
    systemHealth: "Sistem Sağlığı",
    notifications: "Bildirimler",
    analytics: "Kullanım Analitiği",
    fallback: "Ayarlar",
  },
  accessDenied: {
    title: "Erişim Reddedildi",
    description: "Bu alana erişim yetkiniz bulunmamaktadır.",
    returnToPlatform: "Platforma Dön",
  },
  actions: {
    logout: "Çıkış Yap",
    returnToPlatform: "Platforma Dön",
  },
} as const;
