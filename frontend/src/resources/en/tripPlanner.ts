export const tripPlannerText = {
  tabLabel: "Smart Plan",
  title: "Smart Trip Planning",
  intro:
    'After selecting date + route, click "Get Recommendations" and the system will present 3 vehicle + 3 driver candidates.',
  fetchButton: "Get Recommendations",
  retryButton: "Retry",
  loading: "Evaluating candidates…",
  sections: {
    vehicles: "Recommended Vehicles",
    drivers: "Recommended Drivers",
  },
  errors: {
    missingRoute: "First select a date and route.",
    fetch: "Recommendations could not be retrieved. Try again.",
    flagOff: "Trip planning wizard is disabled.",
    forbidden: "You do not have permission for this operation.",
    empty: "No candidates found matching these criteria. Use the manual form.",
  },
  risk: {
    low: "Weather: Low risk",
    medium: "Weather: Medium risk",
    high: "Weather: High risk",
    unknown: "Weather: No data",
  },
  routeTypeLabels: {
    highway_dominant: "Highway Dominant",
    mountain: "Mountain",
    urban: "Urban",
    mixed: "Mixed",
  } as const,
  coldStart: {
    vehicle: "New vehicle",
    driver: "New driver",
  },
  card: {
    score: "Score",
    predicted: "Predicted consumption",
    liters: "L",
    age: "Age",
    similar: "Similar trip",
    whyButton: "Why this?",
  },
  selected: "Selected",
  selectAndContinue: "Select & Continue",
  confirmSelection:
    "Selected vehicle + driver will be transferred to the detail step.",
  xai: {
    title: "Why this recommendation?",
    vehicleSubtitle: "Vehicle score breakdown",
    driverSubtitle: "Driver score breakdown",
    totalScore: "Total score",
    weightSuffix: "weight",
    vehicleFactors: {
      fuel: "Fuel efficiency",
      route_history: "Route history",
      vehicle_health: "Vehicle health",
      availability: "Availability",
    },
    driverFactors: {
      route_type_perf: "Route type performance",
      overall_hybrid: "Hybrid score",
      availability: "Availability",
    },
    reasonsHeading: "Reasons",
    noReasons: "Reasons list is empty.",
    close: "Close",
    meta: {
      similar: "Similar trip count",
      predicted: "Predicted consumption",
      age: "Vehicle age",
      deviation: "Deviation",
      routeType: "Route type",
    },
  },
} as const;

export type TripPlannerText = typeof tripPlannerText;
