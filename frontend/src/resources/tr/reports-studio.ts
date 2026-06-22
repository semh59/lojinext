export const reportsStudioText = {
  heading: "Rapor Stüdyosu",
  description:
    "Hazır şablonlardan rapor oluşturun. Filo geneli, araç bazlı ve yönetim özetleri.",
  galleryTitle: "Şablon Kütüphanesi",
  galleryEmpty: "Henüz şablon yüklenmedi.",
  galleryError: "Şablonlar yüklenemedi.",
  configTitle: "Yapılandırma",
  configHint: "Bir şablon seçin",
  periodLabel: "Periyot",
  periodOptions: {
    current_month: "Bu Ay",
    last_month: "Geçen Ay",
    last_3_months: "Son 3 Ay",
    last_year: "Son 12 Ay",
  } as const,
  formatLabel: "Format",
  vehicleLabel: "Araç",
  vehicleAll: "Tüm filo",
  downloadButton: "İndir",
  downloading: "Hazırlanıyor...",
  downloadSuccess: "Rapor indirildi.",
  downloadError: "Rapor indirilemedi.",
  categoryLabels: {
    executive: "Yönetim",
    fleet: "Filo",
    fuel: "Yakıt",
    compliance: "Uyum",
  } as const,
};

export type PeriodKey = keyof typeof reportsStudioText.periodOptions;
