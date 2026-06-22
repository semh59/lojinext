import { Guzergah } from "../types";

export interface TripImpactRequest {
  cikis_lat: number;
  cikis_lon: number;
  varis_lat: number;
  varis_lon: number;
  trip_date: string;
}

export function buildTripImpactRequest(
  route: Partial<Guzergah> | null | undefined,
  tripDate: string,
): TripImpactRequest | null {
  const cikisLat = route?.cikis_lat;
  const cikisLon = route?.cikis_lon;
  const varisLat = route?.varis_lat;
  const varisLon = route?.varis_lon;

  if (
    typeof cikisLat !== "number" ||
    typeof cikisLon !== "number" ||
    typeof varisLat !== "number" ||
    typeof varisLon !== "number"
  ) {
    return null;
  }

  return {
    cikis_lat: cikisLat,
    cikis_lon: cikisLon,
    varis_lat: varisLat,
    varis_lon: varisLon,
    trip_date: tripDate,
  };
}
