export { aiApi } from "../../api/ai";
export { authApi, fetchWithAuth, tokenStorage } from "./auth-service";
export {
  adminApi,
  adminHealthApi,
  adminImportsApi,
  adminMaintenanceApi,
  adminMlApi,
  adminNotificationsApi,
  adminUsersApi,
} from "../../api/admin";
export { driverService, driverService as driversApi } from "../../api/drivers";
export {
  executiveService,
  executiveService as executiveApi,
} from "../../api/executive";
export { fuelService } from "../../api/fuel";
export { locationService } from "../../api/locations";
export { notificationService } from "../../api/notifications";
export { reportService, reportService as reportsApi } from "../../api/reports";
export { predictionService } from "../../api/predictions";
export { tripService } from "../../api/trips";
export {
  vehicleService,
  vehicleService as vehiclesApi,
} from "../../api/vehicles";
export { weatherApi } from "../../api/weather";
export { wsService } from "./ws-service";
