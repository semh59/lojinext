import { useTranslation } from "react-i18next";

import * as trTrips from "./tr/trips";
import * as enTrips from "./en/trips";
import * as trAdmin from "./tr/admin";
import * as enAdmin from "./en/admin";
import * as trVehicles from "./tr/vehicles";
import * as enVehicles from "./en/vehicles";
import * as trDrivers from "./tr/drivers";
import * as enDrivers from "./en/drivers";
import * as trFuel from "./tr/fuel";
import * as enFuel from "./en/fuel";
import * as trFleet from "./tr/fleet";
import * as enFleet from "./en/fleet";
import * as trLocations from "./tr/locations";
import * as enLocations from "./en/locations";
import * as trTrailers from "./tr/trailers";
import * as enTrailers from "./en/trailers";
import * as trCoaching from "./tr/coaching";
import * as enCoaching from "./en/coaching";
import * as trExecutive from "./tr/executive";
import * as enExecutive from "./en/executive";
import * as trShared from "./tr/shared";
import * as enShared from "./en/shared";
import * as trToday from "./tr/today";
import * as enToday from "./en/today";
import * as trReports from "./tr/reports";
import * as enReports from "./en/reports";
import * as trReportsStudio from "./tr/reports-studio";
import * as enReportsStudio from "./en/reports-studio";
import * as trRouteLab from "./tr/routeLab";
import * as enRouteLab from "./en/routeLab";
import * as trTripPlanner from "./tr/tripPlanner";
import * as enTripPlanner from "./en/tripPlanner";
import * as trInvestigations from "./tr/investigations";
import * as enInvestigations from "./en/investigations";
import * as trMaintenancePredictions from "./tr/maintenancePredictions";
import * as enMaintenancePredictions from "./en/maintenancePredictions";

function useIsEn(): boolean {
  const { i18n } = useTranslation();
  return i18n.language.startsWith("en");
}

export function useTripsResources() {
  const isEn = useIsEn();
  return isEn ? enTrips : trTrips;
}

export function useAdminResources() {
  const isEn = useIsEn();
  return isEn ? enAdmin : trAdmin;
}

export function useVehiclesResources() {
  const isEn = useIsEn();
  return isEn ? enVehicles : trVehicles;
}

export function useDriversResources() {
  const isEn = useIsEn();
  return isEn ? enDrivers : trDrivers;
}

export function useFuelResources() {
  const isEn = useIsEn();
  return isEn ? enFuel : trFuel;
}

export function useFleetResources() {
  const isEn = useIsEn();
  return isEn ? enFleet : trFleet;
}

export function useLocationsResources() {
  const isEn = useIsEn();
  return isEn ? enLocations : trLocations;
}

export function useTrailersResources() {
  const isEn = useIsEn();
  return isEn ? enTrailers : trTrailers;
}

export function useCoachingResources() {
  const isEn = useIsEn();
  return isEn ? enCoaching : trCoaching;
}

export function useExecutiveResources() {
  const isEn = useIsEn();
  return isEn ? enExecutive : trExecutive;
}

export function useSharedResources() {
  const isEn = useIsEn();
  return isEn ? enShared : trShared;
}

export function useTodayResources() {
  const isEn = useIsEn();
  return isEn ? enToday : trToday;
}

export function useReportsResources() {
  const isEn = useIsEn();
  return isEn ? enReports : trReports;
}

export function useReportsStudioResources() {
  const isEn = useIsEn();
  return isEn ? enReportsStudio : trReportsStudio;
}

export function useRouteLabResources() {
  const isEn = useIsEn();
  return isEn ? enRouteLab : trRouteLab;
}

export function useTripPlannerResources() {
  const isEn = useIsEn();
  return isEn ? enTripPlanner : trTripPlanner;
}

export function useInvestigationsResources() {
  const isEn = useIsEn();
  return isEn ? enInvestigations : trInvestigations;
}

export function useMaintenancePredictionsResources() {
  const isEn = useIsEn();
  return isEn ? enMaintenancePredictions : trMaintenancePredictions;
}
