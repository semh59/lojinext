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
  heading: "System Analysis & Reports",
  description:
    "Manage fleet performance reports, cost analyses, and investment impact from here.",
  tabs: {
    overview: "Overview",
    pdf: "PDF Reports",
    cost: "Cost Analysis",
    roi: "Savings & ROI",
    vehicle: "Vehicle Comparison",
    comparison: "Period Comparison",
  } satisfies Record<ReportTabId, string>,
  exportSuccessTitle: "Ready",
  exportSuccessMessage: "Report downloaded successfully.",
  exportErrorTitle: "Error",
  exportErrorMessage: "Report could not be generated.",
  costLoading: "Preparing data...",
  overviewKpi: {
    totalTrips: "Total Trips",
    totalKm: "Total KM",
    fleetAvg: "Fleet Average",
    todayTrips: "Today's Trips",
    trend: (pct: number) =>
      pct > 0
        ? `+${pct.toFixed(1)}% vs last month`
        : `${pct.toFixed(1)}% vs last month`,
    trendNeutral: "No month-over-month comparison",
    consumptionTitle: "6-Month Consumption Trend",
    consumptionUnit: "Litres",
    consumptionEmpty: "No consumption data found.",
    loading: "Loading...",
  },
  comparison: {
    title: "Period Comparison",
    subtitle: "This period vs previous period",
    week: "This Week",
    month: "This Month",
    current: "Current Period",
    previous: "Previous Period",
    fuelL: "Fuel (L)",
    fuelCost: "Cost (TL)",
    anomalies: "Anomalies",
    trips: "Trips",
    noData: "Could not load comparison data.",
    loading: "Loading...",
  },
};

export const reportDownloadOptions = {
  fleet_summary: {
    exportType: "fleet_summary",
    cardTitle: "Fleet Summary",
    cardDescription: "Overall fleet performance, fuel, and cost summary.",
    dialogTitle: "Fleet Summary",
    dialogDescription:
      "Contains overall performance data for the entire fleet.",
  },
  vehicle_detail: {
    exportType: "vehicle_report",
    cardTitle: "Vehicle Detail Report",
    cardDescription: "Trip and consumption details for selected vehicles.",
    dialogTitle: "Vehicle Report",
    dialogDescription:
      "Analyzes trip and consumption details of a specific vehicle.",
  },
  driver_comparison: {
    exportType: "driver_comparison",
    cardTitle: "Driver Comparison",
    cardDescription: "Driver scores and violation analyses.",
    dialogTitle: "Driver Comparison",
    dialogDescription:
      "Compares driver performance, consumption, and violation data.",
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
  downloadButton: "Download PDF",
};

export const reportChartText = {
  title: "Monthly Cost Analysis",
  subtitle: "Operational expense distribution for the last 12 months",
  fuel: "FUEL",
  maintenance: "MAINTENANCE",
  total: "TOTAL",
};

export const reportRoiText = {
  title: "Investment Analysis",
  description:
    "Savings and investment impact are shown only when real cost data is available.",
  roiUnavailable:
    "ROI summary cannot be calculated right now. Investment returns are not shown without source cost data.",
  savingsUnavailable:
    "Savings summary is currently unavailable. Savings cards are not shown until real cost data arrives.",
  investmentAmount: "Investment Amount",
  rangeMin: "10k",
  rangeMax: "500k",
  targetConsumptionTitle: "Target Consumption",
  targetConsumptionPrefix: "Current average of",
  targetConsumptionMiddle: "calculated against a target of",
  targetConsumptionSuffix: "",
  targetConsumptionUnavailable:
    "Target improvement summary is not shown until real consumption data arrives.",
  monthlyPotential: "Monthly Potential",
  annualSavings: "Annual Savings",
  roiMetricTitle: "ROI (Return on Investment)",
  roiMetricUnavailable:
    "ROI card remains empty if real cost data is insufficient.",
  strongImpactMessage: (paybackMonths: number) =>
    `Strong investment impact: payback period ${paybackMonths.toFixed(
      1,
    )} months.`,
};

export const reportExportDialogText = {
  fileFormat: "File Format",
  pdfLabel: "PDF Report",
  pdfDescription: "Visual and analysis focused",
  excelLabel: "Excel Table",
  excelDescription: "Data and list focused",
  startDate: "Start Date",
  endDate: "End Date",
  vehicleSelection: "Vehicle Selection",
  month: "Month",
  year: "Year",
  vehiclesLoading: "Loading vehicles...",
  vehicleNotFound: "Vehicle not found",
  vehicleLoadError: "Vehicle list could not be loaded.",
  selectVehicleError: "Please select a vehicle.",
  exportError: "Export operation could not be completed.",
  cancel: "Cancel",
  preparing: "Preparing...",
  downloaded: "Downloaded",
  downloadPdf: "Download PDF",
  downloadExcel: "Download Excel",
};
