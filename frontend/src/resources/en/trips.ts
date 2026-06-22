export const tripPageText = {
  heading: "Trip Management",
  description:
    "Manage all shipments and anomaly analyses in the system from here.",
} as const;

export const tripHeaderText = {
  title: "Trip Management",
  subtitlePrimary: "Operational Control",
  subtitleSecondary: "Logistics Tracking System",
  showAnalytics: "Fuel Performance",
  hideAnalytics: "Close Panel",
  createTrip: "New Trip",
  createTripAria: "Create New Trip",
} as const;

export const tripStatsText = {
  heading: "Trip Performance Indicators",
  totalTripsLabel: (isCompletedView: boolean) =>
    `${isCompletedView ? "Total Completed" : "Total"} Trips`,
  cancelledLabel: "Cancelled",
  roadCharacter: "Road Character",
  highwayShare: (value: number) => `${value}% Highway`,
  totalAscent: "Total Ascent",
  totalWeight: "Total Tonnage",
  weightUnit: "Ton",
} as const;

export const tripModuleText = {
  approvalQueueBanner: (count: number) =>
    `${count} trip${count === 1 ? "" : "s"} awaiting Telegram approval`,
  bulkApprove: "Approve Selected",
  lastUpdated: (sec: number) => `last updated: ${sec}s ago`,
  loadErrorTitle: "Data Could Not Be Loaded",
  loadErrorForbidden:
    "You do not have permission to view trips. Check role permissions.",
  loadErrorGeneric: "Please check your internet connection and try again.",
  retry: "Retry",
  createSuccess: "New trip saved successfully.",
  createErrorFallback: "Trip could not be saved.",
  updateSuccess: "Trip information updated.",
  updateConflict:
    "This record has been updated by someone else. Please refresh the page and try again.",
  updateErrorFallback: "An error occurred during update.",
  deleteSuccess: "Trip deleted.",
  deleteErrorFallback: "Delete operation failed.",
  returnSuccess: "Return trip created successfully.",
  returnErrorFallback: "Return trip could not be created.",
  bulkStatusSuccess: (count: number) =>
    `${count} trip${count === 1 ? "" : "s"} updated.`,
  bulkStatusError: (count: number) =>
    `${count} trip${count === 1 ? "" : "s"} could not be updated.`,
  bulkCancelSuccess: (count: number) =>
    `${count} trip${count === 1 ? "" : "s"} cancelled.`,
  bulkCancelError: (count: number) =>
    `${count} trip${count === 1 ? "" : "s"} could not be cancelled.`,
  bulkDeleteSuccess: (count: number) =>
    `${count} trip${count === 1 ? "" : "s"} successfully deleted.`,
  bulkDeleteError: (count: number) =>
    `${count} trip${count === 1 ? "" : "s"} could not be deleted.`,
  bulkDeleteFallback: "An error occurred during bulk delete.",
  deleteConfirm: "Are you sure you want to delete this trip?",
  returnConfirm:
    "An automatic return trip will be created for this trip. Do you confirm?",
  bulkDeleteConfirm: (count: number) =>
    `Are you sure you want to delete ${count} trip${count === 1 ? "" : "s"}?`,
  statusTransitionMissing: (status: string) =>
    `No transition from status '${status}'.`,
  statusPrompt: (allowedStatuses: string) => `New status (${allowedStatuses}):`,
  invalidStatus: "Invalid status selected.",
  cancellationReasonPrompt:
    "Enter cancellation reason (at least 5 characters):",
  cancellationReasonInvalid:
    "Cancellation reason must be at least 5 characters.",
  exportLoading: "Preparing Excel file, please wait...",
  exportSuccess: "Excel file downloaded successfully.",
  exportError: "An error occurred during export.",
  exportFileNamePrefix: "trips_export",
  templateFileName: "trip_upload_template.xlsx",
  templateSuccess: "Template downloaded.",
  templateError: "Template could not be downloaded.",
  importSuccess: (count: number) =>
    `${count} trip${count === 1 ? "" : "s"} uploaded successfully.`,
  importError: "File could not be uploaded.",
  totalRecords: (count: number) =>
    `Total ${count.toLocaleString("en-US")} Records`,
  previousPage: "Previous",
  nextPage: "Next",
} as const;

export const tripFilterText = {
  todayFilter: "Today",
  searchPlaceholder: "Search trip number, vehicle, or driver...",
  openFilters: "Filter",
  advancedFiltersTitle: "Advanced Filters",
  advancedFiltersDescription: "Narrow down records",
  statusLabel: "Trip Status",
  dateRangeLabel: "Date Range",
  savedFiltersLabel: "My Saved Filters",
  reset: "Reset",
  apply: "Apply",
  saveCurrentFilter: "Save Current Filter",
  saveDialogTitle: "Save Filter",
  filterNameLabel: "Filter Name",
  filterNamePlaceholder: "E.g.: Active Trips",
  cancel: "Cancel",
  save: "Save",
  saveNameRequired: "Please enter a name for the filter.",
  saveSuccess: "Filter saved.",
  saveError: "Filter could not be saved.",
  deleteSuccess: "Filter deleted.",
  deleteError: "Filter could not be deleted.",
  resetSuccess: "Filters reset.",
  tabs: {
    all: "All",
    planned: "Planned",
    completed: "Completed",
    canceled: "Cancelled",
  },
} as const;

export const tripTableText = {
  emptyTitle: "No Trips Yet",
  emptyDescription:
    "There are no active operational trips recorded in the system.",
  filteredEmptyTitle: "No Results Found",
  filteredEmptyDescription:
    "We could not find records matching the selected filters. Please update the criteria.",
  clearFilters: "Clear All Filters",
  fallbackTripNumber: (id?: number) => `Trip #${id ?? "-"}`,
  unknownValue: "Unknown",
  noTrailer: "No Trailer",
  vehicleLabel: "Operational Vehicle",
  driverLabel: "Responsible Driver",
  trailerFallback: (id: number) => `Trailer #${id}`,
  updateStatus: "Update Status",
  createReturn: "Return Trip",
  costAnalysis: "Cost Analysis",
  deleteTrip: "Delete Trip",
  openMenu: "Trip Actions",
  selectedTrips: "Selected Trip",
  bosSefer: "Empty Trip",
  roundTrip: "Return",
  versionLabel: (v: number) => `v${v}`,
  actualConsumption: "Actual Consumption",
  delayed: (min: number) => `+${min} min delayed`,
  early: (min: number) => `-${min} min early`,
  odometerWarning: (diff: number) =>
    `Km difference: ${diff > 0 ? "+" : ""}${diff} km`,
  rejectionReason: "Rejection Reason",
} as const;

export const tripAnalyticsText = {
  insufficientTitle: "Insufficient Analysis Data",
  insufficientDescription:
    "We do not yet have enough data for in-depth comparison. At least 3 completed and estimated trips are required.",
  kpis: {
    mae: { label: "MAE", description: "Mean Absolute Error" },
    rmse: { label: "RMSE", description: "Root Mean Square Error" },
    compared: { label: "Matched", description: "Compared Dataset" },
    highDeviation: {
      label: "High Deviation",
      description: "Above 15% Threshold",
    },
  },
  trend: {
    title: "Prediction Trend",
    description: "Actual vs Predicted Comparison",
    predicted: "Predicted",
    actual: "Actual",
  },
  distribution: {
    title: "Deviation Distribution",
    description: "Frequency of Error Classes",
    good: "Good",
    warning: "Acceptable",
    error: "Deviation",
  },
  outliers: {
    title: "Highest Deviations (Outliers)",
    description: "Trips with the highest loss rate",
    missingPlate: "No Plate",
    deviationLabel: "Deviation",
  },
} as const;

export const tripBulkActionText = {
  selectedTrips: "Selected Trip",
  updateStatus: "Update Status",
  cancel: "Cancel",
  bulkDelete: "Bulk Delete",
} as const;

export const tripBulkStatusModalText = {
  title: "Bulk Status Update",
  selectedTrips: (count: number) =>
    `${count} Trip${count === 1 ? "" : "s"} Selected`,
  description: "Bulk update selected trips to planned or completed status.",
  planned: "Planned",
  completed: "Completed",
  cancelHint:
    'Bulk cancellation is done from a separate flow. Use the "Cancel" action for cancellations.',
  cancel: "Cancel",
  confirm: "Update",
} as const;

export const tripBulkCancelModalText = {
  title: "Bulk Trip Cancellation",
  summary: (count: number) =>
    `${count} Trip${count === 1 ? "" : "s"} Will Be Cancelled`,
  description: "This action cannot be undone, but can be manually re-planned.",
  reasonLabel: "Cancellation Reason (Required)",
  reasonPlaceholder: "E.g.: Vehicle breakdown, customer cancellation...",
  reasonHint: "Cannot be cancelled without sharing a reason.",
  cancel: "Cancel",
  confirm: "Cancel Trips",
} as const;

export const tripFormModalText = {
  validation: {
    dateRequired: "Date is required.",
    invalidTime: "Invalid time format (HH:mm).",
    tripNumberMax: "Maximum 50 characters allowed.",
    vehicleRequired: "Vehicle selection is required.",
    driverRequired: "Driver selection is required.",
    routeRequired: "Route selection is required.",
    departureRequired: "Departure location is required.",
    arrivalRequired: "Arrival location is required.",
    distancePositive: "Distance must be greater than 0.",
    weightNonNegative: "Weight fields cannot be negative.",
  },
  titles: {
    readOnly: "Trip Details",
    edit: "Update Trip",
    create: "New Trip Entry",
  },
  tabs: {
    details: "Trip Details",
    timeline: "Transaction History",
  },
  statusLabel: "Operational Status",
  actions: {
    close: "Close Window",
    cancel: "Cancel",
    submitting: "Processing...",
    saveUpdate: "Save Update",
    approveTrip: "Approve Trip",
  },
  formError: "Please check the errors in the form.",
} as const;

export const tripDateTimeSectionText = {
  heading: "Timing Index",
  dateLabel: "Operation Date",
  timeLabel: "Departure Time",
  referenceLabel: "Trip / Work Reference",
  referencePlaceholder: "E.g.: TRIP-2026-001",
} as const;

export const tripRouteSelectorText = {
  heading: "Route Planning",
  emptyOption: "Please select a route...",
  inactiveTag: "(INACTIVE)",
  requiredErrorFallback: "Route selection is required.",
  inactiveWarning:
    "Warning: The selected route is inactive in the system. Please contact the administrator.",
  distanceUnit: "KM",
} as const;

export const tripStaffVehicleSectionText = {
  heading: "Asset and Personnel Assignment",
  vehicleLabel: "Operational Vehicle",
  vehiclePlaceholder: "Select vehicle...",
  trailerLabel: "Trailer (Optional)",
  trailerPlaceholder: "No trailer",
  driverLabel: "Responsible Driver",
  driverPlaceholder: "Assign driver...",
} as const;

export const tripLoadManagementSectionText = {
  heading: "Cargo and Load Parameters",
  emptyWeightLabel: "Empty Weight (KG)",
  loadedWeightLabel: "Loaded Weight (KG)",
  summaryTitle: "Net Carrying Capacity",
  summarySubtitle: "Operational load calculation",
  unit: "KG",
} as const;

export const tripTelemetrySectionText = {
  heading: "Route and Telemetry Summary",
  departureLabel: "Departure",
  arrivalLabel: "Arrival",
  distanceUnit: "KM",
  distanceErrorTitle: "Critical Distance Error",
  emptyTitle: "Route Data Awaiting",
  emptyDescription:
    "Please plan a route from the menu above for telemetry analysis.",
} as const;

export const tripRoundTripSelectorText = {
  none: "One Way",
  empty: "Empty Return",
  loaded: "Loaded Return",
} as const;

export const tripRoundTripSectionText = {
  heading: "Linked Return Trip (Automatic)",
  tripNumberLabel: "Return Trip ID/No",
  tripNumberPlaceholder: "System will assign",
  returnLoadLabel: "Return Load Weight (KG)",
  returnLoadPlaceholder: "0",
} as const;

export const tripListText = {
  emptyTitle: "No Active Trips",
  emptyDescription: "No planned trips found.",
  missingPlate: "No plate",
  vehicleLabel: "Vehicle",
  missingDriver: "No driver",
  driverLabel: "Driver",
  unknownStatus: "Unknown",
} as const;

export const tripTimelineText = {
  eventLabels: {
    CREATE: "Creation",
    UPDATE: "Update",
    STATUS_CHANGE: "Status Change",
    PREDICTION_REFRESH: "Prediction Refresh",
    RECONCILIATION: "Reconciliation",
    DELETE: "Deletion",
  },
  empty: "No operation records yet.",
  technicalDetails: "Technical Details",
  predictionInfo: "Prediction Information",
  fieldChanges: "Field Changes",
  model: "Model",
  version: "Version",
  confidence: "Confidence",
  fallback: "Fallback",
  yes: "Yes",
  no: "No",
} as const;
