export const fuelPageText = {
  heading: "Fuel Management",
  description:
    "Manage consumption analysis, cost tracking, and fuel efficiency.",
  notifications: {
    updateSuccessTitle: "Updated",
    updateSuccessMessage: "Record updated successfully.",
    createSuccessTitle: "Added",
    createSuccessMessage: "New fuel record added.",
    actionErrorTitle: "Error",
    actionErrorMessage: "Operation failed.",
    deleteConfirm: "Are you sure you want to delete this record?",
    deleteSuccessTitle: "Success",
    deleteSuccessMessage: "Record deleted.",
    deleteErrorFallback: "Could not be deleted.",
    exportSuccessTitle: "Success",
    exportSuccessMessage: "Excel downloaded.",
    exportErrorMessage: "Export failed.",
    templateErrorMessage: "Template could not be downloaded.",
    importSuccessTitle: "Success",
    importSuccessMessage: "Imported successfully.",
    importErrorMessage: "Import failed.",
  },
  exportFileNamePrefix: "fuel_tracking",
  templateFileName: "fuel_import_template.xlsx",
} as const;

export const fuelHeaderText = {
  addRecord: "Add New Record",
} as const;

export const fuelFilterText = {
  vehiclePlaceholder: "Select vehicle...",
  apply: "Apply",
  reset: "Clear",
} as const;

export const fuelStatsText = {
  unavailable:
    "Fuel statistics are currently unavailable. Summary cards are not shown until real data arrives.",
  totalConsumption: "Total Consumption",
  totalCost: "Total Cost",
  averageConsumption: "Average Consumption",
  averagePrice: "Average Price",
  totalDistance: "Total Distance",
  fuelAnomalies: "Fuel Anomalies",
  fuelAnomaliesSubtitle: "detected in the last 30 days",
  verifiedDataHint: "only verified period data is shown",
} as const;

export const fuelTableText = {
  emptyTitle: "No Records Found",
  emptyDescription: "No fuel records match the filters you set.",
  headers: {
    dateTime: "Date & Time",
    plate: "Vehicle Plate",
    stationReceipt: "Station / Receipt No",
    liters: "Amount (Litres)",
    unitPrice: "Unit Price",
    totalAmount: "Total Amount",
    actions: "Action",
  },
  defaults: {
    time: "12:00",
    station: "Unknown",
    receipt: "-",
  },
  receiptLabel: "Receipt",
  actions: {
    edit: "Edit",
    delete: "Delete",
  },
} as const;

export const fuelPaginationText = {
  totalRecords: (count: number) =>
    `Total ${count.toLocaleString("en-US")} records`,
  firstPage: "First page",
  previous: "Previous",
  next: "Next",
  lastPage: "Last page",
  pageSummary: (currentPage: number, totalPages: number) =>
    `Page ${currentPage} / ${totalPages}`,
} as const;

export const fuelComparisonText = {
  unavailableTitle: "Insufficient Data",
  unavailableDescription:
    "At least 1 trip with both predicted and actual consumption data is required for comparison.",
  averageErrorLabel: "Average Error",
  performanceTitle: "Model Performance",
  maeUnit: "L/100km (MAE)",
  rmseValue: (value: number) => `RMSE value: ${value.toFixed(2)} L/100km`,
  accuracyTitle: "Accuracy Distribution",
  accuracy: {
    good: "Under 5% (good)",
    warning: "5%-15% (acceptable)",
    error: "Over 15% (deviation)",
    tripCount: (count: number) => `${count} trip${count === 1 ? "" : "s"}`,
  },
  analysisLabel: "Prediction Analysis",
  trendTitle: "Predicted vs Actual Trend",
  legend: {
    predicted: "Predicted",
    actual: "Actual",
  },
  tooltip: {
    ratio: "Ratio",
  },
  summary: (totalCompared: number) =>
    `This chart is generated with data from the last ${totalCompared} trips.`,
  summaryHint: "Model accuracy improves as MAE approaches zero.",
} as const;

export const fuelModalText = {
  editTitle: "Edit Fuel Record",
  createTitle: "New Fuel Record",
  description: "Enter vehicle fuel purchase details.",
  labels: {
    date: "Date",
    vehicle: "Vehicle",
    station: "Station",
    liters: "Litres",
    unitPrice: "Unit Price",
    total: "Total (Automatic)",
    odometer: "Odometer",
    receiptNumber: "Receipt Number",
    tankStatus: "Tank Status",
  },
  placeholders: {
    vehicle: "Select",
    station: "E.g.: Shell Station",
    receiptNumber: "E.g.: REC-123",
  },
  tankStatusOptions: {
    full: "Full Tank",
    partial: "Partial Fill",
    unknown: "Unknown",
  },
  actions: {
    cancel: "Cancel",
    save: "Save",
  },
  validation: {
    dateRequired: "Date is required",
    vehicleRequired: "Select a vehicle",
    stationRequired: "Station is required",
    litersPositive: "Litres must be greater than 0",
    unitPricePositive: "Unit price must be greater than 0",
    totalPositive: "Total amount must be 0 or more",
    odometerPositive: "Odometer must be 0 or more",
  },
  enums: {
    partial: "Partial",
    full: "Full",
    pending: "Pending",
    approved: "Approved",
    rejected: "Rejected",
  },
} as const;
