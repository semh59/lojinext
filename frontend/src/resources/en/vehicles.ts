export const vehicleModuleText = {
  notifications: {
    update: {
      title: "Updated",
      description: "Vehicle information updated successfully.",
    },
    create: {
      title: "Added",
      description: "New vehicle added successfully.",
    },
    actionSuccess: {
      title: "Operation Successful",
      description: "Operation completed.",
    },
    errorTitle: "Error",
    saveFallback: "An error occurred during the operation.",
    deleteFallback: "Vehicle could not be deleted.",
    export: {
      successTitle: "Success",
      successDescription: "Excel file prepared.",
      errorDescription: "Export failed.",
    },
    template: {
      successTitle: "Success",
      successDescription: "Template downloaded.",
      errorDescription: "Template could not be downloaded.",
    },
    import: {
      successTitle: "Success",
      successDescription: "Vehicles imported successfully.",
      errorDescription: "Import failed.",
    },
  },
  files: {
    exportPrefix: "vehicles_export",
    templateName: "vehicle_upload_template.xlsx",
  },
  pagination: {
    page: (currentPage: number, totalPages: number) =>
      `Page ${currentPage} / ${totalPages}`,
  },
} as const;

export const vehicleHeaderText = {
  addButton: "Add New Vehicle",
} as const;

export const vehicleFilterText = {
  searchPlaceholder: "Search vehicle, plate, or brand...",
  activeOnly: "Active Vehicles",
  advancedFilters: "Advanced Filter",
  fields: {
    brand: "Brand",
    model: "Model",
    minYear: "Minimum Year",
    maxYear: "Maximum Year",
  },
  placeholders: {
    brand: "E.g.: Mercedes",
    model: "E.g.: Actros",
    minYear: "2015",
    maxYear: "2024",
  },
  reset: "Clear",
  apply: "Apply",
  skeleton: {
    columns: {
      vehicle: "Vehicle",
      plate: "Plate",
      year: "Year",
      tank: "Tank",
      target: "Target",
      status: "Status",
      actions: "Actions",
    },
  },
} as const;

export const vehicleTableText = {
  emptyTitle: "No Vehicles Added Yet",
  emptyDescription:
    "Add a new vehicle using the button in the top right to start fleet management.",
  title: "Fleet Vehicles",
  totalCount: (count: number) =>
    `Total: ${count} Vehicle${count === 1 ? "" : "s"}`,
  openBreakdown: (count: number) =>
    `${count} open breakdown${count === 1 ? "" : "s"}`,
  status: {
    active: "ACTIVE",
    inactive: "INACTIVE",
  },
  labels: {
    modelYear: "Model Year",
    fuelCapacity: "Fuel Capacity",
    targetConsumption: "Target Consumption (L/100km)",
  },
  actions: {
    insights: "Insights",
    detail: "Details",
    edit: "Edit",
    delete: "Delete",
  },
} as const;

export const vehicleDeleteText = {
  title: {
    soft: "Deactivate Vehicle",
    hard: "Permanently Delete",
  },
  description: {
    soft: (plate: string) =>
      `You are about to deactivate vehicle with plate ${plate}. The vehicle will not appear in default lists but its data will be retained.`,
    hard: (plate: string) =>
      `You are about to permanently delete vehicle with plate ${plate}. This action cannot be undone and all historical data will be removed.`,
  },
  actions: {
    cancel: "Cancel",
    softConfirm: "Deactivate",
    hardConfirm: "Yes, Delete",
  },
} as const;

export const vehicleDetailText = {
  errors: {
    statsUnavailable: "Vehicle statistics are currently unavailable.",
    eventsUnavailable: "Event history is unavailable.",
  },
  status: {
    active: "Active",
    inactive: "Inactive",
  },
  stats: {
    totalTrips: "Total Trips",
    totalDistance: "Total Distance",
    averageConsumption: "Avg. Consumption",
    totalFuel: "Total Fuel",
  },
  efficiency: {
    label: "Efficiency Score",
    efficient: (pct: number) => `+${pct.toFixed(1)}% efficient`,
    inefficient: (pct: number) => `-${pct.toFixed(1)}% loss`,
    noData: "No data",
    targetLabel: "Target Consumption",
    actualLabel: "Actual Average",
  },
  inspection: {
    label: "Inspection Date",
    expiredBadge: "INSPECTION EXPIRED",
    expiringSoonBadge: (days: number) => `${days} DAYS LEFT`,
    okBadge: "Inspection Valid",
  },
  aging: {
    label: (years: number) => `${years} Years Old`,
    degradation: (pct: number) => `Aging Effect: -${pct.toFixed(1)}%`,
  },
  events: {
    title: "Event History",
    noEvents: "No events recorded yet.",
    types: {
      CREATED: "Created",
      RE_ACTIVATED: "Reactivated",
      STATUS_CHANGED: "Status Changed",
      UPDATED: "Updated",
    } as Record<string, string>,
    by: (who: string) => `· ${who}`,
  },
  sections: {
    basic: "Basic Information",
    physics: "Physics Parameters",
    notes: "Notes",
    events: "Event History",
  },
  fields: {
    productionYear: "Production Year",
    tankCapacity: "Tank Capacity",
    targetConsumption: "Target Consumption",
    maxPayload: "Max Payload",
    emptyWeight: "Empty Weight",
    dragCoefficient: "Drag Coefficient (Cd)",
    frontalArea: "Frontal Area",
    engineEfficiency: "Engine Efficiency",
    rollingResistance: "Rolling Resistance",
    inspectionDate: "Inspection Date",
  },
} as const;

export const vehicleCardText = {
  inspection: {
    expired: "INSPECTION EXPIRED",
    expiringSoon: (days: number) => `INSPECTION: ${days}D`,
  },
  aging: {
    badge: (years: number) => `${years} YRS`,
    old: "OLD VEHICLE",
  },
} as const;

export const vehicleModalText = {
  title: {
    edit: "Edit Vehicle",
    create: "Add New Vehicle",
  },
  description: {
    edit: "Update vehicle information",
    create: "Add new vehicle to fleet",
  },
  fields: {
    plate: "Plate *",
    brand: "Brand *",
    model: "Model",
    year: "Year",
    tankCapacity: "Tank Capacity",
    targetConsumption: "Target Consumption",
    notes: "Notes",
    active: "Vehicle Active",
    activeDescription: "Inactive vehicles appear greyed out in the list.",
    physics: "Physics Parameters",
    emptyWeight: "Empty Weight",
    dragCoefficient: "Drag Coefficient (Cd)",
    frontalArea: "Frontal Area",
    engineEfficiency: "Engine Efficiency",
    rollingResistance: "Rolling Resistance",
    maxPayload: "Max Payload Capacity",
  },
  placeholders: {
    plate: "34 ABC 123",
    brand: "Mercedes",
    model: "Actros",
    notes: "Additional information about the vehicle...",
  },
  validation: {
    plateMin: "Plate must be at least 3 characters.",
    brandMin: "Brand must be at least 2 characters.",
  },
  actions: {
    cancel: "Cancel",
    update: "Update",
    create: "Add",
  },
} as const;
