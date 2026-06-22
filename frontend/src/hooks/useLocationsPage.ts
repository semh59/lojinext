import { useState } from "react";
import { toast } from "sonner";

import { useLocations } from "./use-locations";
import { useUrlState } from "./use-url-state";
import { usePageTitle } from "./usePageTitle";
import { locationService } from "../api/locations";
import {
  AnalysisResponse,
  Location,
  LocationCreate,
  LocationUpdate,
} from "../types/location";
import { useLocationsResources } from "../resources/useResources";

const LIMIT = 12;

export function useLocationsPage() {
  const { locationsPageText } = useLocationsResources();
  usePageTitle("Güzergahlar");

  const [filters, setFilters] = useUrlState({
    search: "",
    zorluk: "",
    page: 1,
  });
  const { search, zorluk: zorlukFilter, page } = filters;

  const {
    useGetLocations,
    useCreateLocation,
    useUpdateLocation,
    useDeleteLocation,
  } = useLocations({
    skip: (page - 1) * LIMIT,
    limit: LIMIT,
    zorluk: zorlukFilter || undefined,
    search: search || undefined,
  });

  const { data, isLoading, isFetching, refetch } = useGetLocations();
  const locations = data?.items || [];
  const totalCount = data?.total || 0;
  const totalPages = Math.ceil(totalCount / LIMIT);

  const createMutation = useCreateLocation();
  const updateMutation = useUpdateLocation();
  const deleteMutation = useDeleteLocation();

  const [isFormOpen, setIsFormOpen] = useState(false);
  const [selectedLocation, setSelectedLocation] = useState<Location | null>(
    null,
  );
  const [isAnalysisOpen, setIsAnalysisOpen] = useState(false);
  const [analysisLocation, setAnalysisLocation] = useState<Location | null>(
    null,
  );
  const [analysisData, setAnalysisData] = useState<AnalysisResponse | null>(
    null,
  );
  const [isAnalysisLoading, setIsAnalysisLoading] = useState(false);

  const handleAdd = () => {
    setSelectedLocation(null);
    setIsFormOpen(true);
  };

  const handleEdit = (location: Location) => {
    setSelectedLocation(location);
    setIsFormOpen(true);
  };

  const handleAnalyze = async (location: Location) => {
    setAnalysisLocation(location);
    setIsAnalysisOpen(true);

    if (location.route_analysis) {
      setAnalysisData({
        success: true,
        api_mesafe_km: location.api_mesafe_km || 0,
        api_sure_saat: location.api_sure_saat || 0,
        ascent_m: location.ascent_m || 0,
        descent_m: location.descent_m || 0,
        elevation_profile: [],
        route_analysis: location.route_analysis,
        otoban_mesafe_km: location.otoban_mesafe_km || 0,
        sehir_ici_mesafe_km: location.sehir_ici_mesafe_km || 0,
      });
    } else {
      setAnalysisData(null);
    }

    setIsAnalysisLoading(true);
    try {
      const result = await locationService.analyze(location.id);
      setAnalysisData(result);
      if (result.success) {
        toast.success(locationsPageText.notifications.analysisUpdated);
        refetch();
      }
    } catch {
      toast.error(locationsPageText.notifications.analysisFailed);
    } finally {
      setIsAnalysisLoading(false);
    }
  };

  const handleDelete = async (location: Location) => {
    if (
      !window.confirm(
        locationsPageText.deleteConfirm(
          location.cikis_yeri,
          location.varis_yeri,
        ),
      )
    ) {
      return;
    }
    try {
      await deleteMutation.mutateAsync(location.id);
      toast.success(locationsPageText.notifications.deleteSuccess);
    } catch {
      toast.error(locationsPageText.notifications.deleteFailed);
    }
  };

  const handleSave = async (formData: LocationCreate | LocationUpdate) => {
    try {
      if (selectedLocation) {
        await updateMutation.mutateAsync({
          id: selectedLocation.id,
          data: formData as LocationUpdate,
        });
        toast.success(locationsPageText.notifications.updateSuccess);
      } else {
        await createMutation.mutateAsync(formData as LocationCreate);
        toast.success(locationsPageText.notifications.createSuccess);
      }
      setIsFormOpen(false);
      setSelectedLocation(null);
    } catch {
      toast.error(locationsPageText.notifications.saveFailed);
    }
  };

  const downloadBlob = (blob: Blob, fileName: string) => {
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(anchor);
  };

  const handleDownloadTemplate = async () => {
    try {
      const blob = await locationService.downloadTemplate();
      downloadBlob(blob, locationsPageText.downloadTemplateFileName);
    } catch {
      toast.error(locationsPageText.notifications.templateFailed);
    }
  };

  const handleExport = async () => {
    try {
      const blob = await locationService.exportExcel();
      downloadBlob(blob, locationsPageText.exportFileName);
    } catch {
      toast.error(locationsPageText.notifications.exportFailed);
    }
  };

  const handleImport = async (file: File) => {
    try {
      const result = await locationService.uploadExcel(file);
      toast.success(
        locationsPageText.notifications.importSuccess(result.count),
      );
      refetch();
    } catch {
      toast.error(locationsPageText.notifications.importFailed);
    }
  };

  return {
    // filter / pagination state
    search,
    zorlukFilter,
    page,
    limit: LIMIT,
    setFilters,
    // data
    locations,
    totalCount,
    totalPages,
    isLoading,
    isFetching,
    refetch,
    // kpi input (raw list — page computes kpis via buildKpis)
    // modal state
    isFormOpen,
    setIsFormOpen,
    selectedLocation,
    setSelectedLocation,
    isAnalysisOpen,
    setIsAnalysisOpen,
    analysisLocation,
    setAnalysisLocation,
    analysisData,
    isAnalysisLoading,
    // handlers
    handleAdd,
    handleEdit,
    handleAnalyze,
    handleDelete,
    handleSave,
    handleDownloadTemplate,
    handleExport,
    handleImport,
  };
}
