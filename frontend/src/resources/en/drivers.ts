export const driverModuleText = {
  licenseOptions: ["", "B", "C", "CE", "D", "D1E", "E", "G"],
  notifications: {
    successTitle: "Success",
    updateTitle: "Updated",
    createTitle: "Added",
    scoreUpdatedTitle: "Score Updated",
    errorTitle: "Error",
    deleteSoft: "Driver deactivated.",
    deleteHard: "Driver deleted.",
    updateDescription: "Driver information updated successfully.",
    createDescription: "New driver added successfully.",
    saveFallback: "An error occurred during the operation.",
    scoreFallback: "Score update failed.",
    genericFallback: "Operation failed.",
    exportSuccess: "Excel file prepared.",
    exportError: "Export failed.",
    templateSuccess: "Template downloaded.",
    templateError: "Template could not be downloaded.",
    importSuccess: "Drivers imported successfully.",
    importSuccessWithCounts: (inserted: number, errorCount: number) =>
      errorCount > 0
        ? `${inserted} driver${
            inserted === 1 ? "" : "s"
          } added, ${errorCount} row${errorCount === 1 ? "" : "s"} skipped.`
        : `${inserted} driver${
            inserted === 1 ? "" : "s"
          } imported successfully.`,
    importError: "Import failed.",
    bulkDeleteSuccess: (count: number) =>
      `${count} driver${count === 1 ? "" : "s"} deactivated.`,
  },
  confirm: {
    delete: (name: string) =>
      `Are you sure you want to permanently delete driver ${name}?`,
    deactivate: (name: string) =>
      `Are you sure you want to deactivate driver ${name}?`,
    bulkDelete: (count: number) =>
      `Are you sure you want to deactivate ${count} driver${
        count === 1 ? "" : "s"
      }? You will need to reactivate them to undo this.`,
  },
  files: {
    exportPrefix: "drivers_export",
    templateName: "driver_upload_template.xlsx",
  },
} as const;

export const driverHeaderText = {
  addButton: "Add New Driver",
} as const;

export const driverFilterText = {
  searchPlaceholder: "Search name or phone...",
  views: {
    table: "List",
    grid: "Cards",
  },
  activeOnly: "Active Only",
  allLicenses: "All Licenses",
  licenseSuffix: (value: string) => `Class ${value}`,
  reset: "Reset",
  scoreRange: "Score Range",
  minScore: "Min",
  maxScore: "Max",
} as const;

export const driverGridText = {
  status: {
    active: "Active",
    inactive: "Inactive",
  },
  licenseSuffix: (value: string) => `Class ${value} License`,
  actions: {
    aiAnalysis: "AI Analysis",
    edit: "Edit",
    delete: "Delete",
  },
} as const;

export const driverTableText = {
  columns: {
    driver: "Driver",
    contact: "Contact",
    score: "Score",
    status: "Status",
    actions: "Actions",
  },
  status: {
    active: "Active",
    inactive: "Inactive",
  },
  licenseSuffix: (value: string) => `Class ${value}`,
  actions: {
    aiAnalysis: "AI Analysis",
    score: "Score",
    edit: "Edit",
    delete: "Delete",
  },
} as const;

export const driverPerformanceText = {
  title: "Driver Report Card",
  subtitle: (name: string) => `${name} • AI Performance Analysis`,
  loading: "Analyzing...",
  errorFallback: "Performance data could not be retrieved.",
  totalScore: "Overall Performance Score",
  trends: {
    increasing: "Improving",
    decreasing: "Declining",
    stable: "Stable",
  },
  cards: {
    safety: "Safe Driving",
    eco: "Eco Driving",
    compliance: "Rule Compliance",
  },
  stats: {
    trips: "Analyzed Trips",
    distance: "Total KM",
  },
  tabs: {
    performance: "Performance",
    breakdown: "Score Breakdown",
    routes: "Route Profile",
  },
} as const;

export const driverModalText = {
  title: {
    edit: "Edit Driver",
    create: "Add New Driver",
  },
  description: "Enter driver information.",
  fields: {
    fullName: "Full Name *",
    phone: "Phone",
    licenseClass: "License Class",
    startDate: "Start Date",
    manualScore: "Manual Score",
    notes: "Notes",
    active: "Driver Active",
    activeDescription: "Inactive drivers cannot be assigned to trips.",
  },
  placeholders: {
    fullName: "E.g.: John Smith",
    phone: "+1 555 123 4567",
    notes: "Notes about the driver...",
  },
  validation: {
    nameMin: "Name must be at least 3 characters.",
    nameMax: "Name can be at most 100 characters.",
    phone: "Enter a valid phone number.",
    licenseClass: "Select license class.",
    notesMax: "Notes can be at most 500 characters.",
  },
  scoreRange: {
    low: "0.1 Low",
    high: "2.0 Excellent",
  },
  actions: {
    cancel: "Cancel",
    update: "Update",
    save: "Save",
  },
} as const;

export const driverScoreText = {
  title: "Update Score",
  sections: {
    current: "Current Status",
    manual: "Manual Assessment",
    estimated: "Estimated Hybrid Score",
  },
  labels: {
    currentManual: (value: number) => `Manual: ${value.toFixed(1)}`,
    hybridFormula: "* Hybrid = 60% Performance + 40% Manual Assessment",
  },
  scoreBands: {
    risk: "0.1 At Risk",
    neutral: "1.0 Neutral",
    excellent: "2.0 Excellent",
  },
  levels: {
    excellent: "Excellent",
    good: "Good",
    medium: "Average",
    low: "Low",
    veryLow: "Very Low",
  },
  actions: {
    cancel: "Cancel",
    update: "Update",
  },
  notifications: {
    saveFallback: "An error occurred while updating the score.",
  },
} as const;
