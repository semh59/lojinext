export const adminOverviewText = {
  heading: "System Overview",
  description: "The management panel shows only real service and report data.",
  cards: {
    totalTrips: "Total Trips",
    activeVehicles: "Active Vehicles",
    systemStatus: "System Status",
    database: "Database",
  },
  consumptionTrend: {
    title: "Fuel Consumption Trend",
    description: "Actual consumption totals from last reported periods.",
    empty: "No consumption trend data to display yet.",
  },
  operationalHealth: {
    title: "Operational Health Summary",
    description:
      "Backup and circuit breaker status is read from live health endpoints.",
    circuitBreakers: "Circuit Breakers",
    lastBackup: "Last Backup",
    noBackup: "No backup yet",
  },
} as const;

export const adminMlText = {
  heading: "ML Models & Training",
  description:
    "Monitor the training queue and start training only from real vehicle records.",
  vehicleNotFound: "Vehicle not found",
  startTraining: "Start Training",
  notifications: {
    trainingStarted: "Model training started",
    trainingStartFailed: "Training could not be started",
    selectVehicle: "Select a vehicle to start training",
  },
  cards: {
    totalTasks: "Total Tasks",
    runningTasks: "Running Tasks",
    latestRmse: "Latest RMSE",
    completedTasks: (count: number) =>
      `${count} completed task${count === 1 ? "" : "s"}`,
  },
  table: {
    title: "Training Queue",
    vehicleId: "Vehicle ID",
    status: "Status",
    algorithmRmse: "Algorithm / RMSE",
    duration: "Training Duration",
    detail: "Detail",
    createdAt: "Date",
    vehiclePrefix: "Vehicle",
    secondsShort: "s",
    empty: "No training tasks in queue.",
  },
} as const;

export const adminHealthText = {
  heading: "System Health",
  description:
    "Monitor service statuses, database performance, and circuit breakers.",
  refresh: "Refresh",
  backup: "Take Manual Backup",
  notifications: {
    loadFailed: "System health data could not be loaded",
    resetSuccess: (serviceName: string) =>
      `${serviceName} circuit breaker reset`,
    resetFailed: "Reset failed",
    backupStarted: "Database backup process started",
    backupFailed: "Backup could not be started",
  },
  cards: {
    overallStatus: "Overall Status",
    database: "Database",
    cache: "Redis/Cache",
  },
  circuitBreakers: {
    title: "Service Circuit Breakers",
    serviceName: "Service Name",
    status: "Status",
    failureCount: "Error Count",
    detail: "Detail",
    actions: "Actions",
    reset: "Reset",
    empty: "No circuit breaker information found",
  },
} as const;

export const adminConfigurationText = {
  heading: "Configuration Management",
  description:
    "Manage platform behaviors, ML parameters, and system limits from here.",
  loading: "Loading system settings",
  groupSuffix: "settings",
  reloadRequired: "Reload required",
  valuePlaceholder: "Enter value...",
  actions: {
    save: "Save",
  },
  notifications: {
    loadFailedTitle: "Error",
    loadFailedMessage: "Configurations could not be loaded.",
    saveSuccessTitle: "Success",
    saveSuccessMessage: "Setting saved successfully.",
    saveFailedTitle: "Error",
    saveFailedFallback: "Save failed.",
  },
} as const;

export const adminUsersText = {
  heading: "Users & Roles",
  description:
    "Manage system access permissions, user roles, and active sessions.",
  addUser: "New User",
  loading: "Loading user list",
  headers: {
    identity: "Email / Identity",
    fullName: "Full Name",
    role: "Role",
    status: "Status",
    lastLogin: "Last Login",
  },
  userId: (id: number) => `ID: #${id.toString().slice(-4)}`,
  statuses: {
    active: "Active",
    passive: "Inactive",
  },
  actions: {
    edit: "Edit",
  },
  unassignedRole: "Unassigned",
  empty: "No registered users found",
} as const;

export const adminMaintenanceText = {
  heading: "Maintenance & Repair Center",
  description: "Manage upcoming and overdue maintenance tasks for vehicles.",
  sectionTitle: "Urgent & Upcoming Maintenance",
  loading: "Loading maintenance alerts",
  headers: {
    vehicle: "Vehicle ID",
    maintenanceType: "Maintenance Type",
    plannedDateOrKm: "Planned Date / KM",
    status: "Status",
    actions: "Actions",
  },
  vehiclePrefix: "Vehicle",
  unknownStatus: "Unknown",
  completeAction: "Mark Complete",
  empty: "No urgent maintenance alerts",
  statusLabels: {
    overdue: "Overdue",
    upcoming: "Upcoming",
    default: "Planned",
  },
  notifications: {
    loadFailedTitle: "Error",
    loadFailedMessage: "Maintenance alerts could not be loaded",
    completeSuccessTitle: "Success",
    completeSuccessMessage: "Maintenance marked as complete",
    actionFailedTitle: "Error",
    actionFailedFallback: "Operation failed",
  },
} as const;

export const adminDataManagementText = {
  heading: "Data Import & Rollback",
  description: "View past Excel/CSV imports and roll them back if necessary.",
  sectionTitle: "Import History",
  loading: "Loading import history",
  headers: {
    fileName: "File Name",
    type: "Type",
    createdAt: "Date",
    status: "Status",
    counts: "Records (S/E/T)",
    actions: "Actions",
  },
  rollbackConfirm:
    "Are you sure you want to roll back this import? This action is permanent and will delete related data.",
  rollbackAction: "Roll Back",
  empty: "No import history found",
  statusLabels: {
    completed: "Completed",
    error: "Error",
    rolledBack: "Rolled Back",
    default: "Processing",
  },
  notifications: {
    loadFailedTitle: "Error",
    loadFailedMessage: "Import history could not be loaded",
    rollbackSuccessTitle: "Success",
    rollbackSuccessMessage: "Operation successfully rolled back",
    rollbackFailedTitle: "Error",
    rollbackFailedFallback: "Rollback failed",
  },
} as const;

export const adminNotificationsText = {
  heading: "Notification Management",
  description: "Configure in-system notifications and email rules.",
  addRule: "New Rule",
  sectionTitle: "Active Rules",
  loading: "Loading notification rules",
  headers: {
    eventType: "Event Type",
    channels: "Channels",
    targetRole: "Target Role ID",
    template: "Template",
    status: "Status",
  },
  rolePrefix: "Role",
  statuses: {
    active: "Active",
    passive: "Inactive",
  },
  empty: "No notification rules found.",
  notifications: {
    loadFailedTitle: "Error",
    loadFailedMessage: "Notification rules could not be loaded",
  },
} as const;

export const adminIntegrationsText = {
  heading: "Integration API Keys",
  description:
    "Enter external service (Mapbox, OpenRoute, Groq) API keys here. " +
    "Once entered, a value can never be viewed again — only replaced.",
  loading: "Loading integration statuses",
  writeOnlyNotice:
    "For security, stored keys can never be viewed — only replaced.",
  statusLabels: {
    configured: "Configured",
    notConfigured: "Not configured",
  },
  botStatus: {
    label: "Bot Status",
    active: "Active",
    unhealthy: "Active (unhealthy)",
    starting: "Starting",
    inactive: "Inactive",
    unknown: "Unknown",
    hint:
      "This service's token is typically provisioned via the container's " +
      "own .env file, not the panel above — bot status reflects the " +
      "container's actual running state.",
  },
  lastUpdated: (date: string) => `Last updated: ${date}`,
  neverUpdated: "Never updated",
  inputPlaceholder: "Enter new API key...",
  actions: {
    save: "Save",
  },
  notifications: {
    loadFailedTitle: "Error",
    loadFailedMessage: "Integration statuses could not be loaded.",
    saveSuccessTitle: "Success",
    saveSuccessMessage: "API key updated.",
    saveFailedTitle: "Error",
    saveFailedFallback: "Failed to update API key.",
    emptyValue: "Please enter an API key.",
  },
  serviceNames: {
    mapbox: "Mapbox",
    openroute: "OpenRoute Service",
    groq: "Groq (LLM)",
    telegram_driver_bot: "Telegram Driver Bot",
    telegram_ops_bot: "Telegram Ops Bot",
  },
} as const;

export const adminLayoutText = {
  nav: {
    overview: "Overview",
    users: "Users",
    roles: "Roles",
    ml: "ML & Models",
    configuration: "Configuration",
    integrations: "Integrations",
    maintenance: "Maintenance & Repair",
    assignment: "Trip Assignment",
    accuracy: "Forecast Accuracy",
    dataManagement: "Data Management",
    systemHealth: "System Health",
    notifications: "Notifications",
    analytics: "Usage Analytics",
    fallback: "Settings",
  },
  accessDenied: {
    title: "Access Denied",
    description: "You do not have permission to access this area.",
    returnToPlatform: "Return to Platform",
  },
  actions: {
    logout: "Log Out",
    returnToPlatform: "Return to Platform",
  },
} as const;
