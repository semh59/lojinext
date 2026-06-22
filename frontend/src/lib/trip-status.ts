export const TRIP_STATUS_VALUES = ["Planlandı", "Tamamlandı", "İptal"] as const;

export type TripStatus = (typeof TRIP_STATUS_VALUES)[number];

export const TRIP_STATUS_PLANLANDI: TripStatus = "Planlandı";
export const TRIP_STATUS_TAMAMLANDI: TripStatus = "Tamamlandı";
export const TRIP_STATUS_IPTAL: TripStatus = "İptal";

export const TRIP_ASSIGNABLE_STATUS_VALUES = [
  TRIP_STATUS_PLANLANDI,
  TRIP_STATUS_TAMAMLANDI,
] as const;

export type TripAssignableStatus =
  (typeof TRIP_ASSIGNABLE_STATUS_VALUES)[number];

export const TRIP_STATUS_TRANSITIONS: Record<
  TripStatus,
  readonly TripStatus[]
> = {
  [TRIP_STATUS_PLANLANDI]: [TRIP_STATUS_TAMAMLANDI, TRIP_STATUS_IPTAL],
  [TRIP_STATUS_TAMAMLANDI]: [],
  [TRIP_STATUS_IPTAL]: [],
};

const LEGACY_TRIP_STATUS_ALIASES: Record<string, TripStatus> = {
  // Backend canonical English values (DB stores these)
  Planned: TRIP_STATUS_PLANLANDI,
  Completed: TRIP_STATUS_TAMAMLANDI,
  Cancelled: TRIP_STATUS_IPTAL,
  planned: TRIP_STATUS_PLANLANDI,
  completed: TRIP_STATUS_TAMAMLANDI,
  cancelled: TRIP_STATUS_IPTAL,
  PLANNED: TRIP_STATUS_PLANLANDI,
  COMPLETED: TRIP_STATUS_TAMAMLANDI,
  CANCELLED: TRIP_STATUS_IPTAL,
  // Legacy Turkish aliases
  Bekliyor: TRIP_STATUS_PLANLANDI,
  "Devam Ediyor": TRIP_STATUS_PLANLANDI,
  Yolda: TRIP_STATUS_PLANLANDI,
  Tamam: TRIP_STATUS_TAMAMLANDI,
  Planlandi: TRIP_STATUS_PLANLANDI,
  Tamamlandi: TRIP_STATUS_TAMAMLANDI,
  Iptal: TRIP_STATUS_IPTAL,
  "PlanlandÄ±": TRIP_STATUS_PLANLANDI,
  "TamamlandÄ±": TRIP_STATUS_TAMAMLANDI,
  "Ä°ptal": TRIP_STATUS_IPTAL,
  "PlanlandÃ„Â±": TRIP_STATUS_PLANLANDI,
  "TamamlandÃ„Â±": TRIP_STATUS_TAMAMLANDI,
  "Ã„Â°ptal": TRIP_STATUS_IPTAL,
  "PlanlandÃƒâ€Ã‚Â±": TRIP_STATUS_PLANLANDI,
  "TamamlandÃƒâ€Ã‚Â±": TRIP_STATUS_TAMAMLANDI,
  "Ãƒâ€Ã‚Â°ptal": TRIP_STATUS_IPTAL,
};

export const normalizeTripStatus = (
  status?: string | null,
): TripStatus | undefined => {
  if (!status) {
    return undefined;
  }

  if ((TRIP_STATUS_VALUES as readonly string[]).includes(status)) {
    return status as TripStatus;
  }

  return LEGACY_TRIP_STATUS_ALIASES[status];
};

export const normalizeTripStatusOrEmpty = (
  status?: string | null,
): TripStatus | "" => normalizeTripStatus(status) ?? "";
