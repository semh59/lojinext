export const fleetPageText = {
  heading: "Fleet Management",
  description:
    "Track your vehicle fleet, driver roster, and trailer inventory from here.",
  tabs: {
    vehicles: "Vehicles",
    drivers: "Drivers",
    trailers: "Trailers",
  },
} as const;

export const fleetInsightsText = {
  labels: {
    vehicles: "Vehicle",
    drivers: "Driver",
    trailers: "Trailer",
    fallback: "Record",
  },
  cards: {
    total: (label: string) => `Total ${label}s`,
    active: (label: string) => `Active ${label}s`,
    trips: "Total Trips",
    recordsUnit: "records",
    inspectionWarning: "Inspection Alert",
    inspectionHint: (expiring: number, overdue: number) =>
      overdue > 0
        ? `${overdue} vehicle${
            overdue === 1 ? "" : "s"
          } with expired inspection`
        : `${expiring} vehicle${expiring === 1 ? "" : "s"} within 30 days`,
  },
} as const;
