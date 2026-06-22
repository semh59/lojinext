import React, { useEffect, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { History, Route, Sparkles } from "lucide-react";
import { PlanWizardStep, type PlanWizardSelection } from "./PlanWizardStep";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import {
  driversApi,
  locationService,
  vehiclesApi,
  weatherApi,
} from "../../services/api";
import { tripService } from "../../api/trips";
import { dorseService } from "../../services/dorseService";
import {
  TRIP_STATUS_PLANLANDI,
  TRIP_STATUS_VALUES,
  normalizeTripStatus,
} from "../../lib/trip-status";
import { buildTripImpactRequest } from "../../lib/route-weather";
import { cn } from "../../lib/utils";
import {
  Dorse,
  Driver,
  Guzergah,
  SeferTimelineItem,
  Trip,
  TripFormData,
  Vehicle,
} from "../../types";
import { DateTimeSection } from "./TripForm/DateTimeSection";
import { LoadManagementSection } from "./TripForm/LoadManagementSection";
import { RouteSelector } from "./TripForm/RouteSelector";
import { StaffVehicleSection } from "./TripForm/StaffVehicleSection";
import { TelemetrySection } from "./TelemetrySection";
import { TripTimeline } from "./TripTimeline";
import { KilometreYakitSection, TripStatusSection } from "./TripFormSections";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import {
  useTripPlannerResources,
  useTripsResources,
} from "../../resources/useResources";

interface TripFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialData: Trip | null;
  onSubmit: (data: TripFormData) => void;
  isSubmitting: boolean;
  initialTab?: "details" | "timeline";
  isReadOnly?: boolean;
}

const normalizeCollection = <T,>(payload: unknown): T[] => {
  if (Array.isArray(payload)) {
    return payload as T[];
  }

  if (payload && typeof payload === "object") {
    const candidate =
      (payload as { items?: unknown; data?: unknown }).items ??
      (payload as { items?: unknown; data?: unknown }).data;
    if (Array.isArray(candidate)) {
      return candidate as T[];
    }
  }

  return [];
};

export const TripFormModal: React.FC<TripFormModalProps> = ({
  isOpen,
  onClose,
  initialData,
  onSubmit,
  isSubmitting,
  initialTab = "details",
  isReadOnly = false,
}) => {
  const { tripPlannerText } = useTripPlannerResources();
  const { tripFormModalText } = useTripsResources();
  const tripSchema = z.object({
    tarih: z.string().min(1, tripFormModalText.validation.dateRequired),
    saat: z
      .string()
      .regex(
        /^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/,
        tripFormModalText.validation.invalidTime,
      ),
    sefer_no: z
      .string()
      .max(50, tripFormModalText.validation.tripNumberMax)
      .optional()
      .or(z.literal("")),
    arac_id: z.coerce
      .number()
      .int()
      .min(1, tripFormModalText.validation.vehicleRequired),
    dorse_id: z.coerce.number().int().optional().or(z.literal(0)).nullable(),
    sofor_id: z.coerce
      .number()
      .int()
      .min(1, tripFormModalText.validation.driverRequired),
    guzergah_id: z.coerce
      .number()
      .int()
      .min(1, tripFormModalText.validation.routeRequired),
    cikis_yeri: z
      .string()
      .min(1, tripFormModalText.validation.departureRequired),
    varis_yeri: z.string().min(1, tripFormModalText.validation.arrivalRequired),
    mesafe_km: z.coerce
      .number()
      .min(0.1, tripFormModalText.validation.distancePositive),
    bos_agirlik_kg: z.coerce
      .number()
      .min(0, tripFormModalText.validation.weightNonNegative)
      .default(0),
    dolu_agirlik_kg: z.coerce
      .number()
      .min(0, tripFormModalText.validation.weightNonNegative)
      .default(0),
    net_kg: z.coerce
      .number()
      .min(0, tripFormModalText.validation.weightNonNegative)
      .default(0),
    bos_sefer: z.boolean().default(false),
    ascent_m: z.coerce.number().default(0),
    descent_m: z.coerce.number().default(0),
    flat_distance_km: z.coerce.number().default(0),
    durum: z.enum(TRIP_STATUS_VALUES).default(TRIP_STATUS_PLANLANDI),
    ton: z.coerce.number().optional(),
    notlar: z.string().optional(),
    baslangic_km: z.coerce.number().int().min(0).optional().nullable(),
    bitis_km: z.coerce.number().int().min(0).optional().nullable(),
    dagitilan_yakit: z.coerce.number().min(0).max(10000).optional().nullable(),
    tuketim: z.coerce.number().min(0).max(1000).optional().nullable(),
    is_round_trip: z.boolean().default(false),
    return_net_kg: z.coerce.number().min(0).default(0),
    return_sefer_no: z.string().optional(),
  });
  type FormTab = "wizard" | "details" | "timeline";
  // Yeni sefer (initialData=null) için wizard default; edit ise details
  const defaultTab: FormTab = !initialData ? "wizard" : initialTab;
  const [activeTab, setActiveTab] = useState<FormTab>(defaultTab);
  const [timeline, setTimeline] = useState<SeferTimelineItem[]>([]);
  const [isTimelineLoading, setIsTimelineLoading] = useState(false);
  const [weatherImpact, setWeatherImpact] = useState<number | null>(null);
  const [weatherLoading, setWeatherLoading] = useState(false);
  const [returnType] = useState<"none" | "empty" | "loaded">("none");

  const {
    register,
    handleSubmit,
    formState: { errors },
    watch,
    setValue,
    reset,
  } = useForm<TripFormData>({
    resolver: zodResolver(tripSchema) as any,
    defaultValues: {
      tarih: new Date().toISOString().split("T")[0],
      saat: new Date().toTimeString().slice(0, 5),
      sefer_no: "",
      arac_id: 0,
      dorse_id: 0,
      sofor_id: 0,
      guzergah_id: 0,
      cikis_yeri: "",
      varis_yeri: "",
      mesafe_km: 0,
      bos_agirlik_kg: 0,
      dolu_agirlik_kg: 0,
      net_kg: 0,
      bos_sefer: false,
      ascent_m: 0,
      descent_m: 0,
      flat_distance_km: 0,
      durum: TRIP_STATUS_PLANLANDI,
      notlar: "",
      is_round_trip: false,
      return_net_kg: 0,
      return_sefer_no: "",
    },
  });

  useEffect(() => {
    if (!isOpen) {
      reset();
      setActiveTab(!initialData ? "wizard" : "details");
    } else if (initialData) {
      reset({
        ...initialData,
        durum: normalizeTripStatus(initialData.durum) ?? TRIP_STATUS_PLANLANDI,
      } as unknown as TripFormData);
    }
  }, [initialData, isOpen, reset]);

  const handleWizardSelect = (sel: PlanWizardSelection) => {
    setValue("arac_id", sel.arac_id);
    setValue("sofor_id", sel.sofor_id);
    setActiveTab("details");
  };

  useEffect(() => {
    if (isOpen && initialData?.id && activeTab === "timeline") {
      const loadTimeline = async () => {
        setIsTimelineLoading(true);
        try {
          const items = await tripService.getTimeline(initialData.id!);
          setTimeline(items);
        } catch (error) {
          console.error("Failed to load trip timeline", error);
        } finally {
          setIsTimelineLoading(false);
        }
      };
      loadTimeline();
    }
  }, [activeTab, initialData?.id, isOpen]);

  const prefersReducedMotion =
    typeof window !== "undefined"
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false;
  const transitionProps = prefersReducedMotion
    ? { duration: 0 }
    : { duration: 0.3 };

  useEffect(() => {
    if (returnType === "none") {
      setValue("is_round_trip", false);
      setValue("return_net_kg", 0);
    } else {
      setValue("is_round_trip", true);
    }
  }, [returnType, setValue]);

  const { data: routeData } = useQuery({
    queryKey: ["routes", "all"],
    queryFn: () => locationService.getAll({ limit: 1000 }),
  });
  const routes = normalizeCollection<Guzergah>(routeData);

  const { data: vehicleData } = useQuery({
    queryKey: ["vehicles", "active"],
    queryFn: () => vehiclesApi.getAll({ aktif_only: true }),
  });
  const vehicles = normalizeCollection<Vehicle>(vehicleData);

  const { data: driverData } = useQuery({
    queryKey: ["drivers", "active"],
    queryFn: () => driversApi.getAll({ aktif_only: true }),
  });
  const drivers = normalizeCollection<Driver>(driverData);

  const { data: trailerData } = useQuery({
    queryKey: ["trailers", "active"],
    queryFn: () => dorseService.getAll({ aktif_only: true }),
  });
  const trailers = normalizeCollection<Dorse>(trailerData);

  const watchedRouteId = watch("guzergah_id");
  const watchedEmptyWeight = watch("bos_agirlik_kg");
  const watchedLoadedWeight = watch("dolu_agirlik_kg");
  const watchedDate = watch("tarih");
  const watchedDeparture = watch("cikis_yeri");
  const watchedArrival = watch("varis_yeri");
  const selectedRoute = routes.find(
    (route) => route.id === Number(watchedRouteId),
  );

  useEffect(() => {
    const emptyWeight = Number(watchedEmptyWeight || 0);
    const loadedWeight = Number(watchedLoadedWeight || 0);
    setValue("net_kg", Math.max(0, loadedWeight - emptyWeight));
  }, [setValue, watchedEmptyWeight, watchedLoadedWeight]);

  useEffect(() => {
    if (watchedRouteId && routes) {
      const matchedRoute = routes.find(
        (route) => route.id === Number(watchedRouteId),
      );
      if (matchedRoute) {
        setValue("cikis_yeri", matchedRoute.cikis_yeri);
        setValue("varis_yeri", matchedRoute.varis_yeri);
        setValue("mesafe_km", matchedRoute.mesafe_km);
        setValue("ascent_m", matchedRoute.ascent_m || 0);
        setValue("descent_m", matchedRoute.descent_m || 0);
        setValue("flat_distance_km", matchedRoute.flat_distance_km || 0);
      }
    }
  }, [routes, setValue, watchedRouteId]);

  useEffect(() => {
    const weatherRequest = buildTripImpactRequest(selectedRoute, watchedDate);
    if (weatherRequest) {
      const timer = setTimeout(async () => {
        setWeatherLoading(true);
        try {
          const impact = await weatherApi.getTripImpact(weatherRequest);
          setWeatherImpact(impact.fuel_impact_factor ?? null);
        } catch {
          setWeatherImpact(null);
        } finally {
          setWeatherLoading(false);
        }
      }, 1000);

      return () => clearTimeout(timer);
    }

    setWeatherImpact(null);
  }, [selectedRoute, watchedDate]);

  const modalTitle = isReadOnly
    ? tripFormModalText.titles.readOnly
    : initialData
      ? tripFormModalText.titles.edit
      : tripFormModalText.titles.create;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={modalTitle} size="lg">
      <form
        noValidate
        autoComplete="off"
        onSubmit={handleSubmit(
          (data) => onSubmit(data),
          (validationErrors) => {
            console.error("Trip form validation failed", validationErrors);
            toast.error(tripFormModalText.formError);
          },
        )}
        className="relative space-y-6"
      >
        {(initialData || !isReadOnly) && (
          <div className="relative z-20 mb-8 flex rounded-[20px] border border-border/40 bg-elevated/40 p-1 shadow-inner">
            {!initialData && (
              <button
                type="button"
                onClick={() => setActiveTab("wizard")}
                className={cn(
                  "flex flex-1 items-center justify-center gap-3 rounded-[16px] py-3.5 text-[10px] font-black uppercase tracking-[0.2em] transition-all duration-300",
                  activeTab === "wizard"
                    ? "bg-accent text-white shadow-xl shadow-accent/20"
                    : "text-tertiary hover:bg-elevated hover:text-primary",
                )}
              >
                <Sparkles size={16} strokeWidth={2.5} />
                {tripPlannerText.tabLabel}
              </button>
            )}
            <button
              type="button"
              onClick={() => setActiveTab("details")}
              className={cn(
                "flex flex-1 items-center justify-center gap-3 rounded-[16px] py-3.5 text-[10px] font-black uppercase tracking-[0.2em] transition-all duration-300",
                activeTab === "details"
                  ? "bg-accent text-white shadow-xl shadow-accent/20"
                  : "text-tertiary hover:bg-elevated hover:text-primary",
              )}
            >
              <Route size={16} strokeWidth={2.5} />
              {tripFormModalText.tabs.details}
            </button>
            {initialData && (
              <button
                type="button"
                onClick={() => setActiveTab("timeline")}
                className={cn(
                  "flex flex-1 items-center justify-center gap-3 rounded-[16px] py-3.5 text-[10px] font-black uppercase tracking-[0.2em] transition-all duration-300",
                  activeTab === "timeline"
                    ? "bg-accent text-white shadow-xl shadow-accent/20"
                    : "text-tertiary hover:bg-elevated hover:text-primary",
                )}
              >
                <History size={16} strokeWidth={2.5} />
                {tripFormModalText.tabs.timeline}
              </button>
            )}
          </div>
        )}

        <div
          className={cn(
            "space-y-6 transition-all duration-300",
            isReadOnly && "opacity-100",
          )}
        >
          <AnimatePresence mode="wait">
            {activeTab === "wizard" ? (
              <motion.div
                key="wizard"
                initial={
                  prefersReducedMotion ? { opacity: 1 } : { opacity: 0, x: -10 }
                }
                animate={{ opacity: 1, x: 0 }}
                exit={
                  prefersReducedMotion ? { opacity: 1 } : { opacity: 0, x: 10 }
                }
                transition={transitionProps}
                className="space-y-4"
              >
                <PlanWizardStep
                  payload={
                    watchedDate &&
                    watch("mesafe_km") &&
                    Number(watch("mesafe_km")) > 0
                      ? {
                          tarih: watchedDate,
                          guzergah_id: watchedRouteId
                            ? Number(watchedRouteId)
                            : null,
                          cikis_yeri: watchedDeparture || "—",
                          varis_yeri: watchedArrival || "—",
                          mesafe_km: Number(watch("mesafe_km")),
                          ascent_m: Number(watch("ascent_m") || 0),
                          descent_m: Number(watch("descent_m") || 0),
                          flat_distance_km: Number(
                            watch("flat_distance_km") || 0,
                          ),
                          weight_kg: Number(watch("net_kg") || 0),
                          top_n: 3,
                        }
                      : null
                  }
                  onSelectAndContinue={handleWizardSelect}
                />
                <div className="rounded-card border border-border bg-elevated/30 p-3 text-[11px] text-secondary">
                  Önce sağdaki tarih + güzergah alanlarını doldurun, sonra
                  "Önerileri Getir" ile akıllı plan sunulsun.
                </div>
                <fieldset className="m-0 space-y-4 border-none p-0">
                  <RouteSelector
                    register={register}
                    errors={errors}
                    routes={routes}
                    watchedGuzergahId={watchedRouteId}
                    isReadOnly={isReadOnly}
                  />
                  <DateTimeSection
                    register={register}
                    errors={errors}
                    isReadOnly={isReadOnly}
                  />
                </fieldset>
              </motion.div>
            ) : activeTab === "details" ? (
              <motion.div
                key="details"
                initial={
                  prefersReducedMotion ? { opacity: 1 } : { opacity: 0, x: -10 }
                }
                animate={{ opacity: 1, x: 0 }}
                exit={
                  prefersReducedMotion ? { opacity: 1 } : { opacity: 0, x: 10 }
                }
                transition={transitionProps}
                className="space-y-6"
              >
                <fieldset
                  disabled={isReadOnly}
                  className="m-0 space-y-6 border-none p-0"
                >
                  <RouteSelector
                    register={register}
                    errors={errors}
                    routes={routes}
                    watchedGuzergahId={watchedRouteId}
                    isReadOnly={isReadOnly}
                  />

                  <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                    <div className="space-y-6">
                      <DateTimeSection
                        register={register}
                        errors={errors}
                        isReadOnly={isReadOnly}
                      />
                      <StaffVehicleSection
                        register={register}
                        errors={errors}
                        vehicles={vehicles}
                        drivers={drivers}
                        trailers={trailers}
                        isReadOnly={isReadOnly}
                      />
                    </div>

                    <div className="space-y-6">
                      <TelemetrySection
                        watchedGuzergahId={watchedRouteId}
                        watchedCikis={watchedDeparture}
                        watchedVaris={watchedArrival}
                        watchedMesafe={watch("mesafe_km")}
                        weatherImpact={weatherImpact}
                        weatherLoading={weatherLoading}
                        errors={errors}
                      />
                      <LoadManagementSection
                        register={register}
                        errors={errors}
                        watchedNetKg={watch("net_kg")}
                        isReadOnly={isReadOnly}
                      />
                    </div>
                  </div>

                  <KilometreYakitSection register={register} />

                  <TripStatusSection
                    register={register}
                    initialData={initialData}
                  />
                </fieldset>
              </motion.div>
            ) : (
              <motion.div
                key="timeline"
                initial={
                  prefersReducedMotion ? { opacity: 1 } : { opacity: 0, x: 10 }
                }
                animate={{ opacity: 1, x: 0 }}
                exit={
                  prefersReducedMotion ? { opacity: 1 } : { opacity: 0, x: -10 }
                }
                transition={transitionProps}
                className="custom-scrollbar min-h-[400px] max-h-[60vh] overflow-y-auto pr-2"
              >
                <TripTimeline items={timeline} isLoading={isTimelineLoading} />
              </motion.div>
            )}
          </AnimatePresence>

          <div className="relative z-10 mt-4 flex w-full items-center justify-between gap-4 border-t border-border/20 pt-8">
            <Button
              type="button"
              variant="secondary"
              onClick={onClose}
              className="h-14 rounded-xl bg-elevated px-8 text-[10px] font-black uppercase tracking-widest text-tertiary border-border/40 hover:bg-surface hover:text-primary"
            >
              {isReadOnly
                ? tripFormModalText.actions.close
                : tripFormModalText.actions.cancel}
            </Button>

            {activeTab === "details" && !isReadOnly && (
              <Button
                type="submit"
                variant="primary"
                isLoading={isSubmitting}
                className="h-14 rounded-xl px-12 text-[10px] font-black uppercase tracking-[0.2em] shadow-2xl shadow-accent/20 hover:shadow-accent/40"
              >
                {isSubmitting
                  ? tripFormModalText.actions.submitting
                  : initialData
                    ? tripFormModalText.actions.saveUpdate
                    : tripFormModalText.actions.approveTrip}
              </Button>
            )}
          </div>
        </div>
      </form>
    </Modal>
  );
};
