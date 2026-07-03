import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

import {
  TRIP_STATUS_IPTAL,
  TRIP_STATUS_TRANSITIONS,
  normalizeTripStatus,
  type TripAssignableStatus,
} from "../lib/trip-status";
import { tripService } from "../api/trips";
import { useTripStore } from "../stores/use-trip-store";
import { Trip } from "../types";
import { useTripsResources } from "../resources/useResources";

const resolveActionErrorMessage = (error: any, fallback: string) => {
  const envelopeMessage = error?.response?.data?.error?.message;
  if (typeof envelopeMessage === "string" && envelopeMessage.trim())
    return envelopeMessage;
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (typeof error?.message === "string" && error.message.trim())
    return error.message;
  return fallback;
};

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(anchor);
}

export function useTripActions() {
  const { t } = useTranslation();
  const { tripModuleText } = useTripsResources();
  const queryClient = useQueryClient();
  const { filters, selectedTrip, setSelectedTrip, toggleForm, clearSelection } =
    useTripStore();

  const [modalMode, setModalMode] = useState<{
    isReadOnly: boolean;
    initialTab: "details" | "timeline";
  }>({ isReadOnly: false, initialTab: "details" });

  const [isBulkStatusOpen, setBulkStatusOpen] = useState(false);
  const [isBulkCancelOpen, setBulkCancelOpen] = useState(false);

  const createMutation = useMutation({
    mutationFn: (data: Omit<Trip, "id" | "created_at" | "ton">) =>
      tripService.create(data),
    onSuccess: () => {
      toast.success(tripModuleText.createSuccess);
      toggleForm(false);
      setSelectedTrip(null);
      queryClient.invalidateQueries({ queryKey: ["trips"] });
      queryClient.invalidateQueries({ queryKey: ["tripStats"] });
    },
    onError: (mutationError: any) => {
      toast.error(
        resolveActionErrorMessage(
          mutationError,
          tripModuleText.createErrorFallback,
        ),
      );
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Trip> }) =>
      tripService.update(id, data),
    onSuccess: () => {
      toast.success(tripModuleText.updateSuccess);
      toggleForm(false);
      queryClient.invalidateQueries({ queryKey: ["trips"] });
    },
    onError: (mutationError: any) => {
      if (mutationError?.response?.status === 409) {
        toast.error(tripModuleText.updateConflict);
        return;
      }
      toast.error(
        resolveActionErrorMessage(
          mutationError,
          tripModuleText.updateErrorFallback,
        ),
      );
    },
  });

  const deleteMutation = useMutation({
    mutationFn: tripService.delete,
    onSuccess: () => {
      toast.success(tripModuleText.deleteSuccess);
      queryClient.invalidateQueries({ queryKey: ["trips"] });
      if (selectedTrip?.id) toggleForm(false);
    },
    onError: (mutationError: any) => {
      toast.error(
        resolveActionErrorMessage(
          mutationError,
          tripModuleText.deleteErrorFallback,
        ),
      );
    },
  });

  const createReturnMutation = useMutation({
    mutationFn: (tripId: number) => tripService.createReturn(tripId),
    onSuccess: () => {
      toast.success(tripModuleText.returnSuccess);
      queryClient.invalidateQueries({ queryKey: ["trips"] });
    },
    onError: (mutationError: any) => {
      toast.error(
        resolveActionErrorMessage(
          mutationError,
          tripModuleText.returnErrorFallback,
        ),
      );
    },
  });

  const bulkStatusMutation = useMutation({
    mutationFn: ({
      ids,
      status,
    }: {
      ids: number[];
      status: TripAssignableStatus;
    }) => tripService.bulkUpdateStatus(ids, status),
    onSuccess: (result) => {
      toast.success(tripModuleText.bulkStatusSuccess(result.success_count));
      if (result.failed_count > 0) {
        toast.error(tripModuleText.bulkStatusError(result.failed_count));
      }
      clearSelection();
      queryClient.invalidateQueries({ queryKey: ["trips"] });
      setBulkStatusOpen(false);
    },
  });

  const bulkCancelMutation = useMutation({
    mutationFn: ({ ids, reason }: { ids: number[]; reason: string }) =>
      tripService.bulkCancel(ids, reason),
    onSuccess: (result) => {
      toast.success(tripModuleText.bulkCancelSuccess(result.success_count));
      if (result.failed_count > 0) {
        toast.error(tripModuleText.bulkCancelError(result.failed_count));
      }
      clearSelection();
      queryClient.invalidateQueries({ queryKey: ["trips"] });
      setBulkCancelOpen(false);
    },
  });

  const onaylaMutation = useMutation({
    mutationFn: (id: number) => tripService.onayla(id),
    onSuccess: (_, id) => {
      toast.success(t("trips.trip_approved", "Trip #{{id}} approved", { id }));
      queryClient.invalidateQueries({ queryKey: ["trips"] });
    },
    onError: () =>
      toast.error(t("trips.trip_approve_failed", "Approval failed")),
  });

  const reddetMutation = useMutation({
    mutationFn: (id: number) => tripService.reddet(id),
    onSuccess: (_, id) => {
      toast.success(t("trips.trip_rejected", "Trip #{{id}} rejected", { id }));
      queryClient.invalidateQueries({ queryKey: ["trips"] });
    },
    onError: () =>
      toast.error(t("trips.trip_reject_failed", "Rejection failed")),
  });

  const bulkDeleteMutation = useMutation({
    mutationFn: (ids: number[]) => tripService.bulkDelete(ids),
    onSuccess: (result) => {
      if (result.success_count > 0) {
        toast.success(tripModuleText.bulkDeleteSuccess(result.success_count));
      }
      if (result.failed_count > 0) {
        toast.error(tripModuleText.bulkDeleteError(result.failed_count));
      }
      clearSelection();
      queryClient.invalidateQueries({ queryKey: ["trips"] });
    },
    onError: (mutationError: any) => {
      toast.error(
        resolveActionErrorMessage(
          mutationError,
          tripModuleText.bulkDeleteFallback,
        ),
      );
    },
  });

  const handleFormSubmit = (data: any) => {
    const payload = {
      ...data,
      arac_id: Number(data.arac_id),
      sofor_id: Number(data.sofor_id),
      dorse_id: data.dorse_id ? Number(data.dorse_id) : null,
      guzergah_id: Number(data.guzergah_id),
      mesafe_km: Number(data.mesafe_km),
      bos_agirlik_kg: Number(data.bos_agirlik_kg || 0),
      dolu_agirlik_kg: Number(data.dolu_agirlik_kg || 0),
      net_kg: Number(data.net_kg || 0),
    };
    if (selectedTrip?.id) {
      updateMutation.mutate({
        id: selectedTrip.id,
        data: { ...payload, version: selectedTrip.version },
      });
      return;
    }
    createMutation.mutate(payload);
  };

  const handleDelete = (trip: Trip) => {
    if (window.confirm(tripModuleText.deleteConfirm) && trip.id) {
      deleteMutation.mutate(trip.id);
    }
  };

  const handleEdit = (trip: Trip) => {
    setModalMode({ isReadOnly: false, initialTab: "details" });
    setSelectedTrip(trip);
    toggleForm(true);
  };

  const handleViewDetails = (trip: Trip) => {
    setModalMode({ isReadOnly: true, initialTab: "timeline" });
    setSelectedTrip(trip);
    toggleForm(true);
  };

  const handleAdd = () => {
    setModalMode({ isReadOnly: false, initialTab: "details" });
    setSelectedTrip(null);
    toggleForm(true);
  };

  const handleStatusChange = (trip: Trip) => {
    if (!trip.id) return;
    const normalizedCurrentStatus = normalizeTripStatus(trip.durum);
    const allowedTransitions = normalizedCurrentStatus
      ? [...TRIP_STATUS_TRANSITIONS[normalizedCurrentStatus]]
      : [];
    if (allowedTransitions.length === 0) {
      toast.error(tripModuleText.statusTransitionMissing(trip.durum || ""));
      return;
    }
    const requested = window.prompt(
      tripModuleText.statusPrompt(allowedTransitions.join(", ")),
      allowedTransitions[0],
    );
    if (!requested) return;
    const requestedStatus = normalizeTripStatus(requested);
    if (!requestedStatus || !allowedTransitions.includes(requestedStatus)) {
      toast.error(tripModuleText.invalidStatus);
      return;
    }
    const payload: Partial<Trip> = { durum: requestedStatus as Trip["durum"] };
    if (requestedStatus === TRIP_STATUS_IPTAL) {
      const reason = window.prompt(tripModuleText.cancellationReasonPrompt, "");
      if (!reason || reason.trim().length < 5) {
        toast.error(tripModuleText.cancellationReasonInvalid);
        return;
      }
      (payload as any).iptal_nedeni = reason.trim();
    }
    updateMutation.mutate({ id: trip.id, data: payload });
  };

  const handleExport = async () => {
    const toastId = toast.loading(tripModuleText.exportLoading);
    try {
      const { skip, limit, ...exportFilters } = filters;
      const blob = await tripService.exportExcel(exportFilters);
      downloadBlob(
        blob,
        `${tripModuleText.exportFileNamePrefix}_${Date.now()}.xlsx`,
      );
      toast.success(tripModuleText.exportSuccess, { id: toastId });
    } catch {
      toast.error(tripModuleText.exportError, { id: toastId });
    }
  };

  const handleDownloadTemplate = async () => {
    try {
      const blob = await tripService.downloadTemplate();
      downloadBlob(blob, tripModuleText.templateFileName);
      toast.success(tripModuleText.templateSuccess);
    } catch {
      toast.error(tripModuleText.templateError);
    }
  };

  const handleImport = async (file: File) => {
    try {
      const result = await tripService.uploadExcel(file);
      queryClient.invalidateQueries({ queryKey: ["trips"] });
      if ((result.failed_count ?? 0) === 0) {
        toast.success(tripModuleText.importSuccess(result.success_count ?? 0));
      }
      return result;
    } catch (uploadError) {
      toast.error(tripModuleText.importError);
      throw uploadError;
    }
  };

  const handleCreateReturn = (trip: Trip) => {
    if (!trip.id) return;
    if (window.confirm(tripModuleText.returnConfirm)) {
      createReturnMutation.mutate(trip.id);
    }
  };

  return {
    modalMode,
    isSubmitting: createMutation.isPending || updateMutation.isPending,
    isBulkStatusOpen,
    isBulkCancelOpen,
    setBulkStatusOpen,
    setBulkCancelOpen,
    handleFormSubmit,
    handleDelete,
    handleEdit,
    handleViewDetails,
    handleAdd,
    handleStatusChange,
    handleExport,
    handleDownloadTemplate,
    handleImport,
    handleCreateReturn,
    bulkStatusMutation,
    bulkCancelMutation,
    bulkDeleteMutation,
    onaylaMutation,
    reddetMutation,
  };
}
