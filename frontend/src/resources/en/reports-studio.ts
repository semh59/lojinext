export const reportsStudioText = {
  heading: "Report Studio",
  description:
    "Generate reports from ready-made templates. Fleet-wide, vehicle-based, and management summaries.",
  galleryTitle: "Template Library",
  galleryEmpty: "No templates loaded yet.",
  galleryError: "Templates could not be loaded.",
  configTitle: "Configuration",
  configHint: "Select a template",
  periodLabel: "Period",
  periodOptions: {
    current_month: "This Month",
    last_month: "Last Month",
    last_3_months: "Last 3 Months",
    last_year: "Last 12 Months",
  } as const,
  formatLabel: "Format",
  vehicleLabel: "Vehicle",
  vehicleAll: "Entire fleet",
  downloadButton: "Download",
  downloading: "Preparing...",
  downloadSuccess: "Report downloaded.",
  downloadError: "Report could not be downloaded.",
  categoryLabels: {
    executive: "Management",
    fleet: "Fleet",
    fuel: "Fuel",
    compliance: "Compliance",
  } as const,
};

export type PeriodKey = keyof typeof reportsStudioText.periodOptions;
