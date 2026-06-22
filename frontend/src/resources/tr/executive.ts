export const executiveText = {
  pageTitle: "Strategic Cockpit",
  pageSubtitle:
    "Filo Verimliliği Endeksi + cross-feature etki + 90 gün projeksiyon",

  fvi: {
    title: "Filo Verimliliği Endeksi",
    outOf: "/ 100",
    trendLabel: "30g trend",
    confidence: "Güven",
    breakdown: {
      fuel: "Yakıt",
      maintenance: "Bakım",
      driver: "Şoför",
      anomaly: "Anomali Kalitesi",
    },
    coldStartWarning:
      "Düşük güven — bazı alt-skorlar veri yetersiz (cold-start)",
  },

  cashflow: {
    title: "90 Gün Cashflow Projeksiyonu",
    legendFuel: "Yakıt",
    legendMaintenance: "Bakım",
    legendPenalty: "Ceza",
    grandTotal: "Toplam",
    assumptions: "Varsayımlar",
    dieselPrice: "Dizel L fiyatı",
    avgBakimCost: "Ort. bakım maliyeti",
    upcomingBakim: "Yaklaşan bakım sayısı",
  },

  busFactor: {
    title: "Bus Factor (Top-N Şoför Riski)",
    subtitle: "En iyi N şoför ayrılırsa yıllık verim kaybı",
    yearlyLoss: "Yıllık tahmini kayıp",
    riskHigh: "Yüksek Risk",
    riskMedium: "Orta Risk",
    riskLow: "Düşük Risk",
    topDriversAnonymized: "Top-N şoför (anonim)",
    score: "Skor",
    yearlyKm: "Yıllık km",
    nLabel: "N (top şoför sayısı)",
    piiNote: "KVKK koruması: ad/soyad/ID gösterilmiyor",
  },

  crossFeature: {
    title: "Cross-Feature Etki (90g)",
    subtitle:
      "D.4 bakım gecikme zararı + A.5 koçluk tasarrufu + B hırsızlık zararı",
    maintenanceLoss: "Bakım gecikme zararı",
    coachingSavings: "Koçluk tasarrufu",
    theftLoss: "Hırsızlık zararı",
    netImpact: "Net etki",
    confidence: "Heuristic güven",
  },

  whatIf: {
    title: "What-If Simülatörü",
    chooseScenario: "Senaryo seç",
    scenarios: {
      fleet_renewal: "Filo Yenileme ROI",
      training: "Koçluk Programı ROI",
      route_portfolio: "Güzergah Portföy Optimizasyonu",
    },
    runButton: "Senaryoyu Çalıştır",
    running: "Çalıştırılıyor...",
    results: {
      yearlySavings: "Yıllık tasarruf",
      upfront: "Ön yatırım",
      payback: "Geri ödeme süresi",
      fiveYearRoi: "5 yıl ROI",
      co2Reduction: "CO2 azaltımı",
      confidence: "Güven",
      monteCarloP10: "P10 (kötümser)",
      monteCarloP50: "P50 (medyan)",
      monteCarloP90: "P90 (iyimser)",
    },
    inputs: {
      maxAgeYears: "Maks. araç yaşı",
      replacementCost: "Araç başına yenileme maliyeti (TL)",
      improvementPct: "Beklenen iyileşme (%)",
      trainingCost: "Şoför başına eğitim maliyeti (TL)",
      dropBottomN: "Elenecek en kötü güzergah sayısı",
      iterations: "Monte Carlo iterasyonu",
    },
    empty: "Bir senaryo seçip çalıştırın.",
  },

  carbon: {
    title: "Karbon Ayak İzi",
    subtitle: "Euro emisyon sınıfı bazında + sektör karşılaştırma",
    totalCo2: "Toplam CO2 (kg)",
    totalKm: "Toplam km",
    co2PerKm: "CO2/km",
    benchmark: "Sektör benchmark",
    deltaAbove: "Benchmark üstü",
    deltaBelow: "Benchmark altı",
    byEuroClass: "Euro sınıfı bazında",
    topEmitters: "Top-10 emitör",
    plaka: "Plaka",
    euroClass: "Sınıf",
    co2Kg: "CO2 (kg)",
    yearlyL: "Yıllık L",
    days7: "7 gün",
    days30: "30 gün",
    days90: "90 gün",
  },

  compliance: {
    title: "Compliance Heatmap",
    subtitle: "Muayene takibi (v1)",
    overdue: "Gecikmiş",
    soon: "Yakında",
    normal: "Normal",
    low: "Düşük risk",
    empty: "Yaklaşan/geçmiş muayene yok",
    columns: {
      entity: "Varlık",
      plaka: "Plaka",
      expiry: "Bitiş tarihi",
      daysUntil: "Kalan gün",
      risk: "Risk",
    },
    entityType: {
      arac: "Araç",
      dorse: "Dorse",
    },
    notes: {
      v2: "v2: SRC + K1/K2/K3 + Tachograph AETR (backlog)",
    },
  },

  pdf: {
    downloadButton: "CEO 1-pager PDF indir",
    downloading: "Hazırlanıyor...",
    notReady: "PDF özelliği henüz hazır değil",
    error: "PDF indirilemedi",
  },

  errors: {
    loadFailed: "Veri yüklenemedi",
    flagOff: "Strategic Cockpit modülü devre dışı",
    forbidden: "Bu sayfayı görüntüleme yetkiniz yok",
  },
} as const;
