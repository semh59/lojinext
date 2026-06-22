export const todayText = {
  pageTitle: "Today",
  pageSubtitle: "Urgent action list + pending actions",

  sections: {
    critical: "Urgent Action",
    pending: "Pending Action",
    empty: "No urgent actions for today",
  },

  tabs: {
    all: "All",
    anomaly: "Anomaly",
    maintenance: "Maintenance",
    investigation: "Investigation",
  } as const,

  severity: {
    critical: "Critical",
    high: "High",
    medium: "Medium",
    low: "Low",
  } as const,

  category: {
    anomaly: "Anomaly",
    maintenance: "Maintenance",
    investigation: "Investigation",
    telegram_approval: "Approval",
    active_trip: "Active Trip",
  } as const,

  counters: {
    activeTrips: "Active trips",
    completedToday: "Completed today",
  },

  quickActions: {
    title: "Quick Access",
    newTrip: "Plan Trip",
    anomalies: "Anomalies",
    drivers: "Drivers",
    executive: "Strategic Cockpit",
  },

  errors: {
    loadFailed: "List could not be loaded",
    flagOff: "Reports v2 disabled",
  },
} as const;

export type TodayText = typeof todayText;
