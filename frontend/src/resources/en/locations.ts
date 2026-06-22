export const locationsPageText = {
  heading: "Location & Route Management",
  description:
    "Manage registered routes, difficulty levels, and route analyses.",
  addRoute: "New Route",
  deleteConfirm: (origin: string, destination: string) =>
    `Are you sure you want to delete the route ${origin} - ${destination}?`,
  notifications: {
    analysisUpdated: "Analysis updated",
    analysisFailed: "Analysis could not be performed.",
    updateSuccess: "Route updated.",
    createSuccess: "New route created.",
    deleteSuccess: "Route deleted.",
    deleteFailed: "Route could not be deleted.",
    saveFailed: "Operation failed.",
    templateFailed: "Template could not be downloaded.",
    exportFailed: "Export failed.",
    importSuccess: (count: number) =>
      `${count} route${count === 1 ? "" : "s"} uploaded.`,
    importFailed: "File could not be uploaded.",
  },
  downloadTemplateFileName: "route_template.xlsx",
  exportFileName: "routes.xlsx",
  kpis: {
    totalRoutes: {
      label: "Total Routes",
      hint: "Records on this page",
    },
    analyzedRoutes: {
      label: "Analyzed Routes",
      hint: "Route analysis available",
    },
    averageDistance: {
      label: "Average Distance",
      hint: "Page average",
    },
    highDifficulty: {
      label: "Hard Level",
      hint: "High difficulty label",
    },
  },
  visibility: {
    title: "Operational Visibility",
    description:
      "This screen shows only registered route and analysis data. No live map or simulated telemetry is used.",
    readyCount: (count: number) =>
      `Analysis data ready for ${count} route${count === 1 ? "" : "s"}`,
    empty: "No route records to display yet",
  },
  searchPlaceholder: "Search route or city...",
  difficultyPlaceholder: "Difficulty level",
  difficultyOptions: {
    normal: "Normal",
    medium: "Medium",
    hard: "Hard",
  },
  pagination: {
    summary: (total: number, shown: number) =>
      `Showing ${shown} of ${total} total records`,
    previous: "Back",
    next: "Next",
  },
} as const;

export const locationListText = {
  headers: {
    routeInfo: "Route Information",
    destination: "Destination",
    distance: "Distance",
    fuelEstimate: "Estimated Fuel",
    difficulty: "Difficulty Level",
    analysis: "Technical Analysis",
    actions: "Actions",
  },
  fuelEstimateTooltip:
    "Estimated fuel = distance × vehicle avg. consumption × load factor (route_analysis.fuel_estimate_cache).",
  emptyTitle: "No Routes Found",
  emptyDescription:
    "There are no operational routes registered in the system yet. Please create your first plan.",
  addRoute: "Define New Route",
  listTitle: "System Registered Routes",
  difficulty: {
    hard: "Mountainous / Hard",
    medium: "Hilly / Medium",
    easy: "Flat / Easy",
  },
  source: {
    verified: "Updated Map Data",
    standard: "Standard Route Data",
    corrected: "Corrected",
  },
  freshness: {
    never: "Never analyzed",
    stale: (days: number) => `${days}d ago`,
    old: (days: number) => `${days}d ago`,
    fresh: (days: number) => (days === 0 ? "Today" : `${days}d ago`),
  },
  analysisMetrics: {
    ascent: "Ascent",
    descent: "Descent",
  },
  actions: {
    analyze: "Analyze",
    edit: "Edit",
    delete: "Delete",
  },
} as const;

export const routeAnalysisCardText = {
  summaryTitle: "Route Summary",
  summarySubtitle: "Road character and slope distribution",
  sourceChip: "Verified Route Analysis",
  roadDistribution: "Road Character Distribution",
  totalRoute: "Total Route",
  roadTypes: {
    highway: "Highway",
    stateRoad: "State Road",
    urban: "Urban",
  },
  roadSpeeds: {
    highway: "85 km/h",
    stateRoad: "65 km/h",
    urban: "35 km/h",
  },
  terrainTitle: "Slope & Topography",
  steepness: {
    flat: "Flat",
    uphill: "Uphill",
    downhill: "Downhill",
  },
  tooltipRatio: "Ratio",
  summaryBoxTitle: "Analysis Summary",
  summaryBoxDescription: (highwayRatio: number) =>
    `${Math.round(
      highwayRatio * 100,
    )}% of the total road on this route is classified as highway. Slope, ascent, and descent distribution is directly used in fuel consumption assessment.`,
} as const;

export const analysisModalText = {
  title: "Route Analysis",
  loading: "Analyzing with OpenRouteService...",
  empty: "No detailed analysis has been done for this route yet.",
  actions: {
    start: "Start Analysis",
    close: "Close",
    rerun: "Re-analyze",
    calibrate: "Calibrate with Trip",
  },
  routeSummary: (origin: string, destination: string, distanceKm: number) =>
    `${origin} → ${destination} (${distanceKm} km)`,
} as const;

export const locationFormText = {
  titles: {
    edit: "Edit Route",
    create: "Add New Route",
  },
  sections: {
    points: "Point Selection",
    summary: "Route Summary",
  },
  inputs: {
    originSearchLabel: "Origin search",
    destinationSearchLabel: "Destination search",
    originPlaceholder: "Search warehouse, factory, or full address",
    destinationPlaceholder: "Search warehouse, factory, or full address",
    searching: "Searching...",
    originCoordinates: "Origin",
    destinationCoordinates: "Destination",
    recalculate: "Recalculate Route",
    distanceLabel: "Distance (km)",
    durationLabel: "Estimated duration",
    ascentLabel: "Ascent",
    descentLabel: "Descent",
    distributionTitle: "Road Distribution",
    highway: "Highway",
    otherRoads: "Urban / other",
    notesPlaceholder: "Operational notes about the route",
  },
  actions: {
    cancel: "Cancel",
    save: "Save",
    update: "Update",
  },
  toasts: {
    selectBothEndpoints: "Please select a result from the list for both points",
    routeCalculated: "Route information calculated",
    routeCalculationFailed: "An error occurred while calculating the route",
    saveFailed: "An error occurred during save",
  },
  validation: {
    originRequired: "Origin point must be selected",
    destinationRequired: "Destination point must be selected",
    distancePositive: "Distance must be greater than 0",
    durationRange: "Duration must be between 0 and 48 hours",
    ascentRange: "Ascent must be between 0 and 10000",
    descentRange: "Descent must be between 0 and 10000",
    notesMax: "Notes can be at most 500 characters",
  },
} as const;
