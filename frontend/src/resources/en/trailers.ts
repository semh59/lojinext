export const trailerModuleText = {
  notifications: {
    deleteSuccess: "Trailer deleted successfully.",
    importSuccess: "Trailers imported successfully.",
    importError: "An error occurred during import.",
    updateSuccess: "Trailer updated successfully.",
    createSuccess: "New trailer added successfully.",
    saveFallback: "An error occurred during save.",
  },
  pagination: {
    previous: "Previous",
    next: "Next",
  },
} as const;

export const trailerHeaderText = {
  title: "Trailer Management",
  description: "Monitor fleet trailers, manage technical details and statuses.",
  addButton: "Add New Trailer",
} as const;

export const trailerFilterText = {
  searchPlaceholder: "Search trailer, plate, or brand...",
  titles: {
    gridView: "Card View",
    listView: "List View",
    activeOnly: "Active Trailers",
    advancedFilters: "Advanced Filter",
  },
  fields: {
    brand: "Brand",
    model: "Model",
    minYear: "Minimum Year",
    maxYear: "Maximum Year",
  },
  placeholders: {
    brand: "E.g.: Krone",
    model: "E.g.: Frigo",
    minYear: "2015",
    maxYear: "2024",
  },
  reset: "Clear",
  apply: "Apply",
} as const;

export const trailerTableText = {
  emptyTitle: "No Trailers Added Yet",
  emptyDescription:
    "Add a new trailer using the button in the top right to start fleet management.",
  title: "Fleet Trailers",
  totalCount: (count: number) =>
    `Total: ${count} Trailer${count === 1 ? "" : "s"}`,
  columns: {
    plateAndBrand: "Plate & Brand",
    typeAndYear: "Type & Year",
    technical: "Technical Parameters",
    status: "Status",
    actions: "Actions",
  },
  status: {
    active: "ACTIVE",
    inactive: "INACTIVE",
  },
  labels: {
    unknownBrand: "Unknown",
    modelSuffix: "Model",
    tireCount: "Tires",
    modelYear: "Model Year",
    emptyWeight: "Empty Weight",
    tireCountCard: "Tire Count",
    pieceSuffix: "pcs",
  },
  actions: {
    detail: "Detail",
    details: "Details",
    edit: "Edit",
    delete: "Delete",
  },
} as const;

export const trailerDetailText = {
  tabs: {
    general: "Overview",
    technical: "Technical Specs",
    maintenance: "Maintenance History",
  },
  status: {
    active: "ACTIVE",
    inactive: "INACTIVE",
  },
  sections: {
    basic: "Basic Information",
    operational: "Operational Status",
    weight: "Weight & Capacity",
    physical: "Physical Parameters",
  },
  fields: {
    plate: "Plate",
    brandModel: "Brand / Model",
    modelYear: "Model Year",
    type: "Type",
    notes: "Notes",
    unspecified: "Not specified",
    emptyWeight: "Empty Weight",
    tireCount: "Tire Count",
    rollingResistance: "Rolling Resistance",
    dragContribution: "Drag Contribution",
    close: "Close",
  },
  maintenance: {
    unavailableTitle: "Maintenance records are currently unavailable.",
    unavailableDescription:
      "Real maintenance history will be shown here when it arrives in the system.",
  },
} as const;

export const trailerDeleteText = {
  title: "Delete Trailer?",
  description: (plate: string) =>
    `Are you sure you want to delete the trailer with plate ${plate}? This action cannot be undone.`,
  confirm: "Permanently Delete Trailer",
  cancel: "Cancel",
} as const;

export const trailerModalText = {
  title: {
    edit: "Edit Trailer",
    create: "Add New Trailer",
  },
  subtitle: {
    edit: (plate: string | undefined) => plate ?? "-",
    create: "Add a new trailer to your fleet",
  },
  sections: {
    basic: "Basic Information",
    technical: "Physics & Technical Parameters",
  },
  fields: {
    plate: "Plate *",
    brand: "Brand",
    type: "Type",
    modelYear: "Model Year",
    inspectionDate: "Inspection Date",
    emptyWeight: "Empty Weight (kg)",
    payload: "Payload Capacity (kg)",
    tireCount: "Tire Count",
    advancedCoefficients: "Advanced Coefficients",
    rollingResistance: "Rolling Resistance (Crr)",
    dragContribution: "Drag Contribution",
    notes: "Notes",
    active: "Active Usage Status",
    activeDescription: "Deactivated trailers cannot be selected for trips.",
  },
  placeholders: {
    plate: "34 ABC 123",
    brand: "Krone, Schmitz, etc.",
    notes: "Maintenance history, tire condition, etc.",
  },
  options: {
    standard: "Standard",
    frigo: "Refrigerated",
    tented: "Tented",
    tipper: "Tipper",
    lowbed: "Lowbed",
  },
  validation: {
    plateMin: "Plate must be at least 3 characters.",
    yearMin: "Year cannot be earlier than 1990.",
    yearMax: "Year cannot be later than next year.",
    positive: "Must be greater than 0.",
    emptyWeightMax: "Empty weight cannot exceed 20,000 kg.",
    payloadMax: "Payload capacity cannot exceed 40,000 kg.",
    tireCountRange: "Tire count must be between 4 and 16.",
    rollingResistanceMax: "Rolling resistance cannot exceed 0.1.",
    dragContributionMax: "Drag contribution cannot exceed 1.0.",
  },
  actions: {
    cancel: "Cancel",
    update: "Update",
    save: "Save",
  },
} as const;
