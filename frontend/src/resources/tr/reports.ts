export type ReportTabId =
  | "pdf"
  | "cost"
  | "roi"
  | "vehicle"
  | "overview"
  | "comparison";
export type ReportDownloadOptionId =
  | "fleet_summary"
  | "vehicle_detail"
  | "driver_comparison";

export const reportPageText = {
  heading: "Sistem Analizi ve Raporlar",
  description:
    "Filo performans raporlarını, maliyet analizlerini ve yatırım etkisini buradan yönetin.",
  tabs: {
    overview: "Genel Bakış",
    pdf: "PDF Raporlar",
    cost: "Maliyet Analizi",
    roi: "Tasarruf ve ROI",
    vehicle: "Araç Karşılaştırma",
    comparison: "Dönem Karşılaştırma",
  } satisfies Record<ReportTabId, string>,
  exportSuccessTitle: "Hazır",
  exportSuccessMessage: "Rapor başarıyla indirildi.",
  exportErrorTitle: "Hata",
  exportErrorMessage: "Rapor oluşturulamadı.",
  costLoading: "Veriler hazırlanıyor...",
  overviewKpi: {
    totalTrips: "Bu Ay Sefer",
    totalKm: "Bu Ay KM",
    fleetAvg: "Filo Ortalaması",
    todayTrips: "Bugün Sefer",
    trend: (pct: number) =>
      pct > 0
        ? `+${pct.toFixed(1)}% geçen aya göre`
        : `${pct.toFixed(1)}% geçen aya göre`,
    trendNeutral: "Geçen ayla karşılaştırma yok",
    consumptionTitle: "6 Aylık Tüketim Trendi",
    consumptionUnit: "Litre",
    consumptionEmpty: "Tüketim verisi bulunamadı.",
    loading: "Yükleniyor...",
  },
  comparison: {
    title: "Dönem Karşılaştırma",
    subtitle: "Bu periyot vs geçen periyot",
    week: "Bu Hafta",
    month: "Bu Ay",
    current: "Bu Dönem",
    previous: "Önceki Dönem",
    fuelL: "Yakıt (L)",
    fuelCost: "Maliyet (TL)",
    anomalies: "Anomali",
    trips: "Sefer",
    noData: "Karşılaştırma verisi alınamadı.",
    loading: "Yükleniyor...",
  },
};

export const reportDownloadOptions = {
  fleet_summary: {
    exportType: "fleet_summary",
    cardTitle: "Filo Özeti",
    cardDescription: "Genel filo performansı, yakıt ve maliyet özeti.",
    dialogTitle: "Filo Özeti",
    dialogDescription: "Tüm filonun genel performans verilerini içerir.",
  },
  vehicle_detail: {
    exportType: "vehicle_report",
    cardTitle: "Araç Detay Raporu",
    cardDescription: "Seçili araçlar için sefer ve tüketim detayları.",
    dialogTitle: "Araç Raporu",
    dialogDescription:
      "Belirli bir aracın sefer ve tüketim detaylarını analiz eder.",
  },
  driver_comparison: {
    exportType: "driver_comparison",
    cardTitle: "Sürücü Karşılaştırma",
    cardDescription: "Sürücü puanları ve ihlal analizleri.",
    dialogTitle: "Sürücü Karşılaştırma",
    dialogDescription:
      "Sürücülerin performans, tüketim ve ihlal verilerini karşılaştırır.",
  },
} as const satisfies Record<
  ReportDownloadOptionId,
  {
    exportType: "fleet_summary" | "vehicle_report" | "driver_comparison";
    cardTitle: string;
    cardDescription: string;
    dialogTitle: string;
    dialogDescription: string;
  }
>;

export const reportCardsText = {
  downloadButton: "PDF İndir",
};

export const reportChartText = {
  title: "Aylık Maliyet Analizi",
  subtitle: "Son 12 ayın operasyonel gider dağılımı",
  fuel: "YAKIT",
  maintenance: "BAKIM",
  total: "TOPLAM",
};

export const reportRoiText = {
  title: "Yatırım Analizi",
  description:
    "Tasarruf ve yatırım etkisi, yalnızca gerçek maliyet verisi mevcutsa gösterilir.",
  roiUnavailable:
    "ROI özeti şu anda hesaplanamıyor. Kaynak maliyet verisi olmadan yatırım getirisi gösterilmiyor.",
  savingsUnavailable:
    "Tasarruf özeti şu anda alınamıyor. Gerçek maliyet verisi gelmeden tasarruf kartları gösterilmiyor.",
  investmentAmount: "Yatırım Tutarı",
  rangeMin: "10k ₺",
  rangeMax: "500k ₺",
  targetConsumptionTitle: "Hedef Tüketim",
  targetConsumptionPrefix: "Mevcut ortalama",
  targetConsumptionMiddle: "seviyesinden",
  targetConsumptionSuffix: "hedefine göre hesaplanır.",
  targetConsumptionUnavailable:
    "Gerçek tüketim verisi gelmeden hedef iyileştirme özeti gösterilmiyor.",
  monthlyPotential: "Aylık Potansiyel",
  annualSavings: "Yıllık Tasarruf",
  roiMetricTitle: "ROI (Yatırım Getirisi)",
  roiMetricUnavailable:
    "Gerçek maliyet verisi yeterli değilse ROI kartı boş kalır.",
  strongImpactMessage: (paybackMonths: number) =>
    `Güçlü yatırım etkisi: geri ödeme süresi ${paybackMonths.toFixed(1)} ay.`,
};

export const reportExportDialogText = {
  fileFormat: "Dosya Formatı",
  pdfLabel: "PDF Rapor",
  pdfDescription: "Görsel ve analiz odaklı",
  excelLabel: "Excel Tablo",
  excelDescription: "Veri ve liste odaklı",
  startDate: "Başlangıç",
  endDate: "Bitiş",
  vehicleSelection: "Araç Seçimi",
  month: "Ay",
  year: "Yıl",
  vehiclesLoading: "Araçlar yükleniyor...",
  vehicleNotFound: "Araç bulunamadı",
  vehicleLoadError: "Araç listesi yüklenemedi.",
  selectVehicleError: "Lütfen bir araç seçin.",
  exportError: "Dışa aktarma işlemi tamamlanamadı.",
  cancel: "Vazgeç",
  preparing: "Hazırlanıyor...",
  downloaded: "İndirildi",
  downloadPdf: "PDF İndir",
  downloadExcel: "Excel İndir",
};
