export const executiveText = {
  pageTitle: "Strategic Cockpit",
  pageSubtitle:
    "Fleet Efficiency Index + cross-feature impact + 90-day projection",

  fvi: {
    title: "Fleet Efficiency Index",
    outOf: "/ 100",
    trendLabel: "30d trend",
    confidence: "Confidence",
    breakdown: {
      fuel: "Fuel",
      maintenance: "Maintenance",
      driver: "Driver",
      anomaly: "Anomaly Quality",
    },
    coldStartWarning:
      "Low confidence — some sub-scores have insufficient data (cold-start)",
  },

  cashflow: {
    title: "90-Day Cashflow Projection",
    legendFuel: "Fuel",
    legendMaintenance: "Maintenance",
    legendPenalty: "Penalty",
    grandTotal: "Total",
    assumptions: "Assumptions",
    dieselPrice: "Diesel price per litre",
    avgBakimCost: "Avg. maintenance cost",
    upcomingBakim: "Upcoming maintenance count",
  },

  busFactor: {
    title: "Bus Factor (Top-N Driver Risk)",
    subtitle: "Annual efficiency loss if top N drivers leave",
    yearlyLoss: "Estimated annual loss",
    riskHigh: "High Risk",
    riskMedium: "Medium Risk",
    riskLow: "Low Risk",
    topDriversAnonymized: "Top-N drivers (anonymous)",
    score: "Score",
    yearlyKm: "Annual km",
    nLabel: "N (top driver count)",
    piiNote: "Privacy protection: names/IDs not shown",
  },

  crossFeature: {
    title: "Cross-Feature Impact (90d)",
    subtitle:
      "D.4 maintenance delay loss + A.5 coaching savings + B theft loss",
    maintenanceLoss: "Maintenance delay loss",
    coachingSavings: "Coaching savings",
    theftLoss: "Theft loss",
    netImpact: "Net impact",
    confidence: "Heuristic confidence",
  },

  whatIf: {
    title: "What-If Simulator",
    chooseScenario: "Choose scenario",
    scenarios: {
      fleet_renewal: "Fleet Renewal ROI",
      training: "Coaching Program ROI",
      route_portfolio: "Route Portfolio Optimization",
    },
    runButton: "Run Scenario",
    running: "Running...",
    results: {
      yearlySavings: "Annual savings",
      upfront: "Upfront investment",
      payback: "Payback period",
      fiveYearRoi: "5-year ROI",
      co2Reduction: "CO2 reduction",
      confidence: "Confidence",
      monteCarloP10: "P10 (pessimistic)",
      monteCarloP50: "P50 (median)",
      monteCarloP90: "P90 (optimistic)",
    },
    inputs: {
      maxAgeYears: "Max vehicle age",
      replacementCost: "Replacement cost per vehicle",
      improvementPct: "Expected improvement (%)",
      trainingCost: "Training cost per driver",
      dropBottomN: "Worst routes to eliminate",
      iterations: "Monte Carlo iterations",
    },
    empty: "Select and run a scenario.",
  },

  carbon: {
    title: "Carbon Footprint",
    subtitle: "By Euro emission class + sector comparison",
    totalCo2: "Total CO2 (kg)",
    totalKm: "Total km",
    co2PerKm: "CO2/km",
    benchmark: "Sector benchmark",
    deltaAbove: "Above benchmark",
    deltaBelow: "Below benchmark",
    byEuroClass: "By Euro class",
    topEmitters: "Top-10 emitters",
    plaka: "Plate",
    euroClass: "Class",
    co2Kg: "CO2 (kg)",
    yearlyL: "Annual L",
    days7: "7 days",
    days30: "30 days",
    days90: "90 days",
  },

  compliance: {
    title: "Compliance Heatmap",
    subtitle: "Inspection tracking (v1)",
    overdue: "Overdue",
    soon: "Soon",
    normal: "Normal",
    low: "Low risk",
    empty: "No upcoming/overdue inspections",
    columns: {
      entity: "Entity",
      plaka: "Plate",
      expiry: "Expiry date",
      daysUntil: "Days remaining",
      risk: "Risk",
    },
    entityType: {
      arac: "Vehicle",
      dorse: "Trailer",
    },
    notes: {
      v2: "v2: SRC + K1/K2/K3 + Tachograph AETR (backlog)",
    },
  },

  pdf: {
    downloadButton: "Download CEO 1-pager PDF",
    downloading: "Preparing...",
    notReady: "PDF feature not ready yet",
    error: "PDF could not be downloaded",
  },

  errors: {
    loadFailed: "Data could not be loaded",
    flagOff: "Strategic Cockpit module is disabled",
    forbidden: "You do not have permission to view this page",
  },
} as const;
