import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  FilterX,
} from "lucide-react";
import { toast } from "sonner";

import { tripService } from "../../api/trips";
import { useTripActions } from "../../hooks/useTripActions";
import { useTripsData } from "../../hooks/useTripsData";
import { BulkActionBar } from "../../components/trips/BulkActionBar";
import { BulkCancelModal } from "../../components/trips/BulkCancelModal";
import { BulkStatusModal } from "../../components/trips/BulkStatusModal";
import { TripAnalytics } from "../../components/trips/TripAnalytics";
import { TripFilters } from "../../components/trips/TripFilters";
import { TripFormModal } from "../../components/trips/TripFormModal";
import { TripHeader } from "../../components/trips/TripHeader";
import { TripStats } from "../../components/trips/TripStats";
import { TripsTodaySummary } from "../../components/trips/TripsTodaySummary";
import { TripCostAnalysisModal } from "../../components/trips/TripCostAnalysisModal";
import { TripTable } from "../../components/trips/TripTable";
import { Button } from "../../components/ui/Button";
import { useTripStore } from "../../stores/use-trip-store";
import { normalizeTripStatusOrEmpty } from "../../lib/trip-status";
import { useQueryClient } from "@tanstack/react-query";
import { useTripsResources } from "../../resources/useResources";
import { useTranslation } from "react-i18next";

export const TripsModule = () => {
  const { t } = useTranslation();
  const { tripModuleText } = useTripsResources();
  const queryClient = useQueryClient();
  const {
    setFilters,
    selectedTrip,
    isFormOpen,
    toggleForm,
    selectedIds,
    toggleSelection,
    clearSelection,
    showCharts,
    toggleCharts,
    resetFilters,
  } = useTripStore();

  const {
    trips,
    totalCount,
    isLoading,
    isError,
    tripLoadErrorMessage,
    stats,
    fuelPerformanceData,
    isFuelPerformanceLoading,
    hasActiveFilter,
    pageSize,
    currentSkip,
    currentPage,
    totalPages,
    beklemedeSayisi,
    dataUpdatedAt,
  } = useTripsData();

  // Diğer sayfalardan filtreli link ile gelindiğinde (ör. dashboard "Bugünkü Seferler"),
  // URL'deki baslangic_tarih/bitis_tarih/durum parametrelerini store'a yansıt.
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    const start = searchParams.get("baslangic_tarih");
    const end = searchParams.get("bitis_tarih");
    const durum = searchParams.get("durum");
    const next: Parameters<typeof setFilters>[0] = {};
    if (start) next.baslangic_tarih = start;
    if (end) next.bitis_tarih = end;
    if (durum) {
      const normalized = normalizeTripStatusOrEmpty(durum);
      if (normalized) next.durum = normalized;
    }
    if (Object.keys(next).length > 0) {
      setFilters(next);
      // Param'ları temizle ki yenileme/back gezintisinde tekrar uygulanmasın.
      setSearchParams({}, { replace: true });
    }
    // Mount-only: consumes a one-time deep-link (e.g. dashboard "Bugünkü
    // Seferler" link) and clears the params so back/refresh doesn't re-apply
    // them. Re-running on every searchParams change would defeat that.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [isBulkApproving, setIsBulkApproving] = useState(false);
  const [costAnalysisSeferId, setCostAnalysisSeferId] = useState<number | null>(
    null,
  );

  const handleBulkApprove = async () => {
    if (selectedIds.length === 0) return;
    setIsBulkApproving(true);
    try {
      await Promise.all(selectedIds.map((id) => tripService.onayla(id)));
      toast.success(t("trips.bulk_approved", { n: selectedIds.length }));
      queryClient.invalidateQueries({ queryKey: ["trips"] });
      queryClient.invalidateQueries({ queryKey: ["tripsBeklemede"] });
      clearSelection();
    } catch {
      toast.error(t("trips.bulk_approve_failed"));
    } finally {
      setIsBulkApproving(false);
    }
  };

  const {
    modalMode,
    isSubmitting,
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
  } = useTripActions();

  return (
    <div className="custom-scrollbar h-full w-full flex-1 overflow-y-auto bg-transparent px-6 py-8 animate-stagger-fade">
      <TripHeader
        onAdd={handleAdd}
        showCharts={showCharts}
        onToggleCharts={() => toggleCharts()}
      />

      <div className="mb-4">
        <TripsTodaySummary />
      </div>

      <TripStats stats={stats} />

      <AnimatePresence>
        {beklemedeSayisi > 0 && (
          <motion.div
            key="approval-banner"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="mb-4 flex items-center gap-3 rounded-modal border border-warning/30 bg-warning/10 px-4 py-3"
          >
            <AlertTriangle size={16} className="shrink-0 text-warning" />
            <p className="text-sm font-bold text-warning">
              {tripModuleText.approvalQueueBanner(beklemedeSayisi)}
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showCharts && (
          <TripAnalytics
            data={fuelPerformanceData}
            isLoading={isFuelPerformanceLoading}
          />
        )}
      </AnimatePresence>

      <TripFilters
        onExport={handleExport}
        onImport={handleImport}
        onDownloadTemplate={handleDownloadTemplate}
        dataUpdatedAt={dataUpdatedAt}
      />

      <div className="mt-4">
        {isError ? (
          <div className="flex flex-col items-center justify-center rounded-modal border border-danger/20 bg-surface p-20">
            <FilterX className="mb-4 h-12 w-12 text-danger/30" />
            <h3 className="text-lg font-bold uppercase tracking-tight text-primary">
              {tripModuleText.loadErrorTitle}
            </h3>
            <p className="mt-1 font-medium text-secondary">
              {tripLoadErrorMessage}
            </p>
            <Button
              variant="primary"
              className="mt-6"
              onClick={() =>
                queryClient.invalidateQueries({ queryKey: ["trips"] })
              }
            >
              {tripModuleText.retry}
            </Button>
          </div>
        ) : (
          <>
            <TripTable
              trips={trips}
              isLoading={isLoading}
              onEdit={handleEdit}
              onDelete={handleDelete}
              onCreateReturn={handleCreateReturn}
              onStatusChange={handleStatusChange}
              onOnayla={(trip) => onaylaMutation.mutate(trip.id!)}
              onReddet={(trip) => reddetMutation.mutate(trip.id!)}
              onCostAnalysis={(trip) =>
                trip.id && setCostAnalysisSeferId(trip.id)
              }
              selectedIds={selectedIds}
              onToggleSelection={toggleSelection}
              onViewDetails={handleViewDetails}
              hasActiveFilter={hasActiveFilter}
              onClearFilters={resetFilters}
            />

            {!isLoading && !isError && totalCount > 0 && (
              <div className="mt-6 flex items-center justify-between rounded-card border border-border bg-surface px-4 py-3">
                <div className="text-xs font-bold uppercase tracking-widest text-secondary">
                  {tripModuleText.totalRecords(totalCount)}
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    className="h-8 shadow-none"
                    disabled={currentSkip === 0}
                    onClick={() =>
                      setFilters({ skip: Math.max(0, currentSkip - pageSize) })
                    }
                  >
                    <ChevronLeft className="h-4 w-4" />
                    {tripModuleText.previousPage}
                  </Button>
                  <div className="rounded-md border border-border bg-elevated px-3 py-1.5 text-xs font-bold text-primary">
                    {currentPage} / {totalPages}
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="h-8 shadow-none"
                    disabled={currentSkip + pageSize >= totalCount}
                    onClick={() => setFilters({ skip: currentSkip + pageSize })}
                  >
                    {tripModuleText.nextPage}
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <TripFormModal
        isOpen={isFormOpen}
        onClose={() => toggleForm(false)}
        initialData={selectedTrip}
        onSubmit={handleFormSubmit}
        isSubmitting={isSubmitting}
        isReadOnly={modalMode.isReadOnly}
        initialTab={modalMode.initialTab}
      />

      <BulkActionBar
        selectedCount={selectedIds.length}
        onClear={clearSelection}
        onStatusUpdate={() => setBulkStatusOpen(true)}
        onCancel={() => setBulkCancelOpen(true)}
        onDelete={() => {
          if (
            window.confirm(tripModuleText.bulkDeleteConfirm(selectedIds.length))
          ) {
            bulkDeleteMutation.mutate(selectedIds);
          }
        }}
        onApprove={handleBulkApprove}
        isApproving={isBulkApproving}
      />

      <BulkStatusModal
        isOpen={isBulkStatusOpen}
        onClose={() => setBulkStatusOpen(false)}
        selectedCount={selectedIds.length}
        onConfirm={(status) =>
          bulkStatusMutation.mutate({ ids: selectedIds, status })
        }
        isSubmitting={bulkStatusMutation.isPending}
      />

      <BulkCancelModal
        isOpen={isBulkCancelOpen}
        onClose={() => setBulkCancelOpen(false)}
        selectedCount={selectedIds.length}
        onConfirm={(reason) =>
          bulkCancelMutation.mutate({ ids: selectedIds, reason })
        }
        isSubmitting={bulkCancelMutation.isPending}
      />

      <TripCostAnalysisModal
        seferId={costAnalysisSeferId}
        onClose={() => setCostAnalysisSeferId(null)}
      />
    </div>
  );
};
