import { zodResolver } from "@hookform/resolvers/zod";
import {
  useMemo,
  useState,
  useEffect,
  useCallback,
  type ChangeEvent,
} from "react";
import { useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import * as z from "zod";

import { useDebounce } from "./useDebounce";
import { GeocodeSuggestion, locationService } from "../api/locations";
import { Location, LocationCreate, RouteAnalysis } from "../types/location";
import { useLocationsResources } from "../resources/useResources";

type EndpointKey = "cikis" | "varis";
type LocationDifficulty = "Normal" | "Orta" | "Zor";

export interface LocationFormValues {
  cikis_yeri: string;
  varis_yeri: string;
  mesafe_km: number;
  tahmini_sure_saat: number;
  zorluk: LocationDifficulty;
  ascent_m: number;
  descent_m: number;
  flat_distance_km?: number;
  otoban_mesafe_km?: number;
  sehir_ici_mesafe_km?: number;
  cikis_lat: number;
  cikis_lon: number;
  varis_lat: number;
  varis_lon: number;
  notlar: string;
}

const EMPTY_VALUES: Partial<LocationFormValues> = {
  cikis_yeri: "",
  varis_yeri: "",
  mesafe_km: 0,
  tahmini_sure_saat: 0,
  zorluk: "Normal",
  ascent_m: 0,
  descent_m: 0,
  flat_distance_km: 0,
  otoban_mesafe_km: 0,
  sehir_ici_mesafe_km: 0,
  notlar: "",
};

const normalizePlaceName = (value: string): string =>
  value
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => {
      const first = word[0];
      const upper =
        first === "i" ? "İ" : first === "ı" ? "I" : first.toUpperCase();
      return upper + word.slice(1).toLowerCase();
    })
    .join(" ");

export const formatDuration = (hours: number): string => {
  if (!hours || hours <= 0) {
    return "00:00:00";
  }
  const totalSeconds = Math.round(hours * 3600);
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s
    .toString()
    .padStart(2, "0")}`;
};

export const formatCoordinate = (value?: number): string =>
  typeof value === "number" && !Number.isNaN(value) ? value.toFixed(6) : "-";

const mapDifficulty = (difficulty?: string): LocationDifficulty => {
  if (difficulty === "Duz" || difficulty === "Normal") {
    return "Normal";
  }
  if (
    difficulty === "Hafif Eğimli" ||
    difficulty === "Hafif Egimli" ||
    difficulty === "Orta"
  ) {
    return "Orta";
  }
  if (
    difficulty === "Dik/Dağlık" ||
    difficulty === "Dik/Daglik" ||
    difficulty === "Zor"
  ) {
    return "Zor";
  }
  return "Normal";
};

interface UseLocationFormProps {
  isOpen: boolean;
  location: Location | null;
  onSave: (data: LocationCreate) => Promise<void>;
  onClose: () => void;
}

export const useLocationForm = ({
  isOpen,
  location,
  onSave,
  onClose,
}: UseLocationFormProps) => {
  const { locationFormText } = useLocationsResources();
  const locationSchema = z.object({
    cikis_yeri: z
      .string()
      .min(2, locationFormText.validation.originRequired)
      .max(100),
    varis_yeri: z
      .string()
      .min(2, locationFormText.validation.destinationRequired)
      .max(100),
    mesafe_km: z
      .number()
      .positive(locationFormText.validation.distancePositive),
    tahmini_sure_saat: z
      .number()
      .min(0, locationFormText.validation.durationRange)
      .max(48, locationFormText.validation.durationRange),
    zorluk: z.enum(["Normal", "Orta", "Zor"]),
    ascent_m: z
      .number()
      .min(0, locationFormText.validation.ascentRange)
      .max(10000, locationFormText.validation.ascentRange),
    descent_m: z
      .number()
      .min(0, locationFormText.validation.descentRange)
      .max(10000, locationFormText.validation.descentRange),
    flat_distance_km: z.number().min(0).optional(),
    otoban_mesafe_km: z.number().min(0).optional(),
    sehir_ici_mesafe_km: z.number().min(0).optional(),
    cikis_lat: z.number().min(-90).max(90),
    cikis_lon: z.number().min(-180).max(180),
    varis_lat: z.number().min(-90).max(90),
    varis_lon: z.number().min(-180).max(180),
    notlar: z.string().max(500, locationFormText.validation.notesMax),
  });
  const {
    register,
    handleSubmit,
    reset,
    control,
    setValue,
    getValues,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<LocationFormValues>({
    resolver: zodResolver(locationSchema),
    defaultValues: EMPTY_VALUES,
  });

  const [isCalculating, setIsCalculating] = useState(false);
  const [routeAnalysisData, setRouteAnalysisData] =
    useState<RouteAnalysis | null>(null);
  const [searchText, setSearchText] = useState<Record<EndpointKey, string>>({
    cikis: "",
    varis: "",
  });
  const [suggestions, setSuggestions] = useState<
    Record<EndpointKey, GeocodeSuggestion[]>
  >({
    cikis: [],
    varis: [],
  });
  const [loadingSuggestions, setLoadingSuggestions] = useState<
    Record<EndpointKey, boolean>
  >({
    cikis: false,
    varis: false,
  });
  const [selectedSuggestion, setSelectedSuggestion] = useState<
    Record<EndpointKey, GeocodeSuggestion | null>
  >({
    cikis: null,
    varis: null,
  });
  const [lastCalculatedKey, setLastCalculatedKey] = useState<string | null>(
    null,
  );

  const watchedDuration = watch("tahmini_sure_saat");
  const originLat = useWatch({ control, name: "cikis_lat" });
  const originLon = useWatch({ control, name: "cikis_lon" });
  const destinationLat = useWatch({ control, name: "varis_lat" });
  const destinationLon = useWatch({ control, name: "varis_lon" });

  const debouncedOrigin = useDebounce(searchText.cikis, 400);
  const debouncedDestination = useDebounce(searchText.varis, 400);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    if (location) {
      reset({
        cikis_yeri: location.cikis_yeri,
        varis_yeri: location.varis_yeri,
        mesafe_km: location.mesafe_km,
        tahmini_sure_saat: location.tahmini_sure_saat || 0,
        zorluk: mapDifficulty(location.zorluk),
        ascent_m: location.ascent_m || 0,
        descent_m: location.descent_m || 0,
        flat_distance_km: location.flat_distance_km || 0,
        otoban_mesafe_km: location.otoban_mesafe_km || 0,
        sehir_ici_mesafe_km: location.sehir_ici_mesafe_km || 0,
        cikis_lat: location.cikis_lat ?? undefined,
        cikis_lon: location.cikis_lon ?? undefined,
        varis_lat: location.varis_lat ?? undefined,
        varis_lon: location.varis_lon ?? undefined,
        notlar: location.notlar || "",
      });
      setSearchText({
        cikis: location.cikis_yeri,
        varis: location.varis_yeri,
      });
      setSelectedSuggestion({
        cikis:
          typeof location.cikis_lat === "number" &&
          typeof location.cikis_lon === "number"
            ? {
                lat: location.cikis_lat,
                lon: location.cikis_lon,
                label: location.cikis_yeri,
                source: "offline",
              }
            : null,
        varis:
          typeof location.varis_lat === "number" &&
          typeof location.varis_lon === "number"
            ? {
                lat: location.varis_lat,
                lon: location.varis_lon,
                label: location.varis_yeri,
                source: "offline",
              }
            : null,
      });
      setRouteAnalysisData(location.route_analysis || null);
    } else {
      reset(EMPTY_VALUES);
      setSearchText({ cikis: "", varis: "" });
      setSelectedSuggestion({ cikis: null, varis: null });
      setRouteAnalysisData(null);
    }

    setSuggestions({ cikis: [], varis: [] });
    setLoadingSuggestions({ cikis: false, varis: false });
    setLastCalculatedKey(null);
  }, [isOpen, location, reset]);

  const searchGeocode = async (
    endpoint: EndpointKey,
    query: string,
    selectedLabel?: string,
  ) => {
    const trimmed = query.trim();
    if (trimmed.length < 2 || trimmed === selectedLabel) {
      setSuggestions((current) => ({ ...current, [endpoint]: [] }));
      return;
    }

    setLoadingSuggestions((current) => ({ ...current, [endpoint]: true }));
    try {
      const results = await locationService.geocode(trimmed);
      setSuggestions((current) => ({ ...current, [endpoint]: results }));
    } catch {
      setSuggestions((current) => ({ ...current, [endpoint]: [] }));
    } finally {
      setLoadingSuggestions((current) => ({ ...current, [endpoint]: false }));
    }
  };

  useEffect(() => {
    void searchGeocode(
      "cikis",
      debouncedOrigin,
      selectedSuggestion.cikis?.label,
    );
  }, [debouncedOrigin, selectedSuggestion.cikis?.label]);

  useEffect(() => {
    void searchGeocode(
      "varis",
      debouncedDestination,
      selectedSuggestion.varis?.label,
    );
  }, [debouncedDestination, selectedSuggestion.varis?.label]);

  const handleSearchInputChange =
    (endpoint: EndpointKey) => (event: ChangeEvent<HTMLInputElement>) => {
      const value = event.target.value;
      setSearchText((current) => ({ ...current, [endpoint]: value }));
      setValue(endpoint === "cikis" ? "cikis_yeri" : "varis_yeri", value, {
        shouldDirty: true,
        shouldValidate: true,
      });

      const selected = selectedSuggestion[endpoint];
      if (selected && selected.label !== value) {
        setSelectedSuggestion((current) => ({ ...current, [endpoint]: null }));
        setSuggestions((current) => ({ ...current, [endpoint]: [] }));
        if (endpoint === "cikis") {
          setValue("cikis_lat", undefined as unknown as number);
          setValue("cikis_lon", undefined as unknown as number);
        } else {
          setValue("varis_lat", undefined as unknown as number);
          setValue("varis_lon", undefined as unknown as number);
        }
      }
    };

  const handleSuggestionSelect = (
    endpoint: EndpointKey,
    suggestion: GeocodeSuggestion,
  ) => {
    setSelectedSuggestion((current) => ({
      ...current,
      [endpoint]: suggestion,
    }));
    setSearchText((current) => ({ ...current, [endpoint]: suggestion.label }));
    setSuggestions((current) => ({ ...current, [endpoint]: [] }));

    if (endpoint === "cikis") {
      setValue("cikis_yeri", suggestion.label, {
        shouldDirty: true,
        shouldValidate: true,
      });
      setValue("cikis_lat", suggestion.lat, {
        shouldDirty: true,
        shouldValidate: true,
      });
      setValue("cikis_lon", suggestion.lon, {
        shouldDirty: true,
        shouldValidate: true,
      });
    } else {
      setValue("varis_yeri", suggestion.label, {
        shouldDirty: true,
        shouldValidate: true,
      });
      setValue("varis_lat", suggestion.lat, {
        shouldDirty: true,
        shouldValidate: true,
      });
      setValue("varis_lon", suggestion.lon, {
        shouldDirty: true,
        shouldValidate: true,
      });
    }
  };

  const calculateRouteKey = useMemo(() => {
    if (
      typeof originLat !== "number" ||
      typeof originLon !== "number" ||
      typeof destinationLat !== "number" ||
      typeof destinationLon !== "number"
    ) {
      return null;
    }
    return `${originLat}:${originLon}:${destinationLat}:${destinationLon}`;
  }, [destinationLat, destinationLon, originLat, originLon]);

  const handleCalculate = useCallback(async () => {
    const values = getValues();
    if (
      typeof values.cikis_lat !== "number" ||
      typeof values.cikis_lon !== "number" ||
      typeof values.varis_lat !== "number" ||
      typeof values.varis_lon !== "number"
    ) {
      toast.error(locationFormText.toasts.selectBothEndpoints);
      return;
    }

    setIsCalculating(true);
    try {
      const data = await locationService.getRouteInfo({
        cikis_lat: values.cikis_lat,
        cikis_lon: values.cikis_lon,
        varis_lat: values.varis_lat,
        varis_lon: values.varis_lon,
      });

      setValue("mesafe_km", data.distance_km ?? 0, {
        shouldDirty: true,
        shouldValidate: true,
      });
      setValue("tahmini_sure_saat", (data.duration_min ?? 0) / 60, {
        shouldDirty: true,
        shouldValidate: true,
      });
      setValue("zorluk", mapDifficulty(data.difficulty as string | undefined), {
        shouldDirty: true,
        shouldValidate: true,
      });
      setValue("ascent_m", data.ascent_m ?? 0);
      setValue("descent_m", data.descent_m ?? 0);
      setValue("flat_distance_km", Number(data.flat_distance_km ?? 0));
      setValue("otoban_mesafe_km", data.otoban_mesafe_km ?? 0);
      setValue("sehir_ici_mesafe_km", data.sehir_ici_mesafe_km ?? 0);

      setRouteAnalysisData(
        (data.route_analysis as RouteAnalysis | undefined) ?? null,
      );
      setLastCalculatedKey(calculateRouteKey);
      toast.success(locationFormText.toasts.routeCalculated);
    } catch (error) {
      console.error("Route calculation error", error);
      toast.error(locationFormText.toasts.routeCalculationFailed);
    } finally {
      setIsCalculating(false);
    }
  }, [
    getValues,
    setValue,
    calculateRouteKey,
    locationFormText.toasts.selectBothEndpoints,
    locationFormText.toasts.routeCalculated,
    locationFormText.toasts.routeCalculationFailed,
  ]);

  useEffect(() => {
    if (
      !isOpen ||
      !calculateRouteKey ||
      calculateRouteKey === lastCalculatedKey
    ) {
      return;
    }
    void handleCalculate();
  }, [calculateRouteKey, isOpen, lastCalculatedKey, handleCalculate]);

  const onSubmit = async (values: LocationFormValues) => {
    try {
      const payload: LocationCreate = {
        ...values,
        cikis_yeri: normalizePlaceName(values.cikis_yeri),
        varis_yeri: normalizePlaceName(values.varis_yeri),
        route_analysis: routeAnalysisData,
      };
      await onSave(payload);
      onClose();
    } catch (error) {
      console.error("Location save error", error);
      toast.error(locationFormText.toasts.saveFailed);
    }
  };

  return {
    // form
    register,
    handleSubmit,
    control,
    errors,
    isSubmitting,
    onSubmit,
    // state
    isCalculating,
    routeAnalysisData,
    searchText,
    suggestions,
    loadingSuggestions,
    // derived / watched
    watchedDuration,
    originLat,
    originLon,
    destinationLat,
    destinationLon,
    calculateRouteKey,
    // handlers
    handleSearchInputChange,
    handleSuggestionSelect,
    handleCalculate,
  };
};
