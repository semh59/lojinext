import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Trash2 } from "lucide-react";
import { DriverModal } from "../drivers/DriverModal";
import { DriverScoreModal } from "../drivers/DriverScoreModal";
import { DriverPerformanceModal } from "../drivers/DriverPerformanceModal";
import { DriverTable } from "../drivers/DriverTable";
import { DriverGrid } from "../drivers/DriverGrid";
import { DriverFilters } from "../drivers/DriverFilters";
import { DriverHeader } from "../drivers/DriverHeader";
import { driverService } from "../../api/drivers";
import { Driver } from "../../types";
import { useNotify } from "../../context/NotificationContext";
import { useUrlState } from "../../hooks/use-url-state";
import { useDebounce } from "../../hooks/useDebounce";
import { useDriversResources } from "../../resources/useResources";
import { useTranslation } from "react-i18next";
export function DriversModule() {
  const { t } = useTranslation();
  const { driverModuleText } = useDriversResources();
  const EHLIYET_OPTIONS = [...driverModuleText.licenseOptions];
  const { notify } = useNotify();
  const queryClient = useQueryClient();

  // Modaller
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isScoreModalOpen, setIsScoreModalOpen] = useState(false);
  const [isPerformanceModalOpen, setIsPerformanceModalOpen] = useState(false);
  const [selectedDriver, setSelectedDriver] = useState<Driver | null>(null);

  // Bulk selection state
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const clearSelection = () => setSelectedIds([]);
  const toggleSelection = (id: number) =>
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  const toggleAll = (allIds: number[], allSelected: boolean) =>
    setSelectedIds((prev) => {
      const set = new Set(prev);
      if (allSelected) {
        allIds.forEach((id) => set.delete(id));
      } else {
        allIds.forEach((id) => set.add(id));
      }
      return Array.from(set);
    });

  // URL State (Synced filters)
  const [urlState, setUrlState] = useUrlState({
    search: "",
    aktif: true as boolean,
    ehliyet: "",
    view: "grid" as "table" | "grid",
    min_score: 0.1,
    max_score: 2.0,
    page: 1,
  });

  const {
    search,
    aktif: aktifOnly,
    ehliyet: ehliyetFilter,
    view: viewMode,
    min_score: minScore,
    max_score: maxScore,
    page,
  } = urlState;
  const limit = 20;

  // Aramayı 300ms debounce et — her tuş vuruşunda istek atılmasın.
  const debouncedSearch = useDebounce(search, 300);

  // Skor range default (0.1, 2.0) ise undefined gönder → backend filtre uygulamaz.
  const minScoreParam = minScore > 0.1 ? minScore : undefined;
  const maxScoreParam = maxScore < 2.0 ? maxScore : undefined;

  // React Query: Fetch Drivers
  const { data, isLoading } = useQuery({
    queryKey: [
      "drivers",
      {
        page,
        search: debouncedSearch,
        aktifOnly,
        ehliyetFilter,
        minScoreParam,
        maxScoreParam,
      },
    ],
    queryFn: () =>
      driverService.getAll({
        skip: (page - 1) * limit,
        limit: limit,
        search: debouncedSearch || undefined,
        aktif_only: aktifOnly,
        ehliyet_sinifi: ehliyetFilter || undefined,
        min_score: minScoreParam,
        max_score: maxScoreParam,
      }),
  });

  const drivers = Array.isArray(data) ? data : data?.items || [];

  // React Query: Mutations
  const deleteMutation = useMutation({
    mutationFn: (driver: Driver) => driverService.delete(driver.id!),
    onSuccess: (_, driver) => {
      notify(
        "success",
        driverModuleText.notifications.successTitle,
        driver.aktif
          ? driverModuleText.notifications.deleteSoft
          : driverModuleText.notifications.deleteHard,
      );
      queryClient.invalidateQueries({ queryKey: ["drivers"] });
    },
    onError: (error: any) => {
      notify(
        "error",
        driverModuleText.notifications.errorTitle,
        error.response?.data?.error?.message ||
          error.response?.data?.detail ||
          driverModuleText.notifications.genericFallback,
      );
    },
  });

  const bulkDeleteMutation = useMutation({
    mutationFn: (ids: number[]) => driverService.bulkDelete(ids),
    onSuccess: (result) => {
      notify(
        "success",
        driverModuleText.notifications.successTitle,
        driverModuleText.notifications.bulkDeleteSuccess(result.deleted ?? 0),
      );
      queryClient.invalidateQueries({ queryKey: ["drivers"] });
      clearSelection();
    },
    onError: (error: any) => {
      notify(
        "error",
        driverModuleText.notifications.errorTitle,
        error.response?.data?.error?.message ||
          error.response?.data?.detail ||
          driverModuleText.notifications.genericFallback,
      );
    },
  });

  const handleBulkDelete = () => {
    if (selectedIds.length === 0) return;
    if (
      !window.confirm(driverModuleText.confirm.bulkDelete(selectedIds.length))
    )
      return;
    bulkDeleteMutation.mutate(selectedIds);
  };

  const handleSave = async (data: Partial<Driver>) => {
    try {
      if (selectedDriver?.id) {
        await driverService.update(selectedDriver.id, data);
        notify(
          "success",
          driverModuleText.notifications.updateTitle,
          driverModuleText.notifications.updateDescription,
        );
      } else {
        await driverService.create(data);
        notify(
          "success",
          driverModuleText.notifications.createTitle,
          driverModuleText.notifications.createDescription,
        );
      }
      queryClient.invalidateQueries({ queryKey: ["drivers"] });
      setIsModalOpen(false);
    } catch (error) {
      notify(
        "error",
        driverModuleText.notifications.errorTitle,
        driverModuleText.notifications.saveFallback,
      );
      throw error;
    }
  };

  const handleScoreSave = async (score: number) => {
    if (!selectedDriver?.id) return;
    try {
      await driverService.updateScore(selectedDriver.id, score);
      notify(
        "success",
        driverModuleText.notifications.scoreUpdatedTitle,
        driverModuleText.notifications.updateDescription,
      );
      queryClient.invalidateQueries({ queryKey: ["drivers"] });
      setIsScoreModalOpen(false);
    } catch (error) {
      notify(
        "error",
        driverModuleText.notifications.errorTitle,
        driverModuleText.notifications.scoreFallback,
      );
      throw error;
    }
  };

  const handleDelete = async (driver: Driver) => {
    if (!driver.id) return;
    const isPassive = !driver.aktif;
    const confirmMsg = isPassive
      ? driverModuleText.confirm.delete(driver.ad_soyad)
      : driverModuleText.confirm.deactivate(driver.ad_soyad);

    if (!window.confirm(confirmMsg)) return;
    deleteMutation.mutate(driver);
  };

  const handleExport = async () => {
    try {
      const blob = await driverService.exportExcel({
        search: debouncedSearch || undefined,
        aktif_only: aktifOnly,
        ehliyet_sinifi: ehliyetFilter || undefined,
        min_score: minScoreParam,
        max_score: maxScoreParam,
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${driverModuleText.files.exportPrefix}_${
        new Date().toISOString().split("T")[0]
      }.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      notify(
        "success",
        driverModuleText.notifications.successTitle,
        driverModuleText.notifications.exportSuccess,
      );
    } catch (error) {
      notify(
        "error",
        driverModuleText.notifications.errorTitle,
        driverModuleText.notifications.exportError,
      );
    }
  };

  const handleDownloadTemplate = async () => {
    try {
      const blob = await driverService.downloadTemplate();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = driverModuleText.files.templateName;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      notify(
        "success",
        driverModuleText.notifications.successTitle,
        driverModuleText.notifications.templateSuccess,
      );
    } catch (error) {
      notify(
        "error",
        driverModuleText.notifications.errorTitle,
        driverModuleText.notifications.templateError,
      );
    }
  };

  const handleImport = async (file: File) => {
    try {
      const res = await driverService.uploadExcel(file);
      // Backend response: { success, message: "N şoför yüklendi.", errors }.
      // Eski kod `res?.inserted` arıyordu (undefined) → kullanıcıya hep 0
      // gösteriyordu. Sayıyı message'ten parse et (regex: leading digits).
      const matched = /^(\d+)\s+/.exec(res?.message ?? "");
      const inserted = matched ? parseInt(matched[1], 10) : 0;
      const errorCount = Array.isArray(res?.errors) ? res.errors.length : 0;
      notify(
        errorCount > 0 ? "warning" : "success",
        driverModuleText.notifications.successTitle,
        driverModuleText.notifications.importSuccessWithCounts(
          inserted,
          errorCount,
        ),
      );
      queryClient.invalidateQueries({ queryKey: ["drivers"] });
      return res;
    } catch (error) {
      notify(
        "error",
        driverModuleText.notifications.errorTitle,
        driverModuleText.notifications.importError,
      );
      throw error;
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-8"
    >
      <DriverHeader
        onAdd={() => {
          setSelectedDriver(null);
          setIsModalOpen(true);
        }}
        onExport={handleExport}
        onDownloadTemplate={handleDownloadTemplate}
        onImport={handleImport as any}
      />

      <DriverFilters
        search={search}
        setSearch={(val) => setUrlState({ search: val, page: 1 })}
        viewMode={viewMode}
        setViewMode={(val) => setUrlState({ view: val })}
        aktifOnly={aktifOnly}
        setAktifOnly={(val) => setUrlState({ aktif: val, page: 1 })}
        ehliyetFilter={ehliyetFilter}
        setEhliyetFilter={(val) => setUrlState({ ehliyet: val, page: 1 })}
        ehliyetOptions={EHLIYET_OPTIONS}
        minScore={minScore}
        setMinScore={(val) => setUrlState({ min_score: val, page: 1 })}
        maxScore={maxScore}
        setMaxScore={(val) => setUrlState({ max_score: val, page: 1 })}
      />

      {isLoading ? (
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="w-10 h-10 border-[3px] border-accent/20 border-t-accent rounded-full animate-spin" />
        </div>
      ) : (
        <>
          <AnimatePresence>
            {viewMode === "table" && selectedIds.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="flex items-center justify-between gap-3 rounded-modal border border-accent/30 bg-accent/5 px-4 py-3"
              >
                <span className="text-xs font-semibold text-primary">
                  {t("drivers.selected_count", "{{n}} drivers selected", {
                    n: selectedIds.length,
                  })}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={clearSelection}
                    className="rounded-card px-3 py-1.5 text-xs font-semibold text-secondary transition-colors hover:bg-elevated hover:text-primary"
                  >
                    {t("drivers.clear_selection", "Clear")}
                  </button>
                  <button
                    onClick={handleBulkDelete}
                    disabled={bulkDeleteMutation.isPending}
                    className="inline-flex items-center gap-1 rounded-card bg-danger px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-danger/90 disabled:opacity-50"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    {t("drivers.deactivate_btn", "Deactivate")}
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {viewMode === "table" ? (
            <div className="bg-surface rounded-[10px] border border-border shadow-sm overflow-hidden">
              <DriverTable
                drivers={drivers}
                onEdit={(d) => {
                  setSelectedDriver(d);
                  setIsModalOpen(true);
                }}
                onDelete={handleDelete}
                onScoreClick={(d) => {
                  setSelectedDriver(d);
                  setIsScoreModalOpen(true);
                }}
                onPerformanceClick={(d) => {
                  setSelectedDriver(d);
                  setIsPerformanceModalOpen(true);
                }}
                selectedIds={selectedIds}
                onToggleSelection={toggleSelection}
                onToggleAll={toggleAll}
              />
            </div>
          ) : (
            <DriverGrid
              drivers={drivers}
              onEdit={(d) => {
                setSelectedDriver(d);
                setIsModalOpen(true);
              }}
              onDelete={handleDelete}
              onPerformanceClick={(d) => {
                setSelectedDriver(d);
                setIsPerformanceModalOpen(true);
              }}
            />
          )}
        </>
      )}

      <DriverModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSave={handleSave}
        driver={selectedDriver}
      />

      <DriverScoreModal
        isOpen={isScoreModalOpen}
        onClose={() => setIsScoreModalOpen(false)}
        onSave={handleScoreSave}
        driver={selectedDriver}
      />

      <DriverPerformanceModal
        isOpen={isPerformanceModalOpen}
        onClose={() => setIsPerformanceModalOpen(false)}
        driver={selectedDriver}
      />
    </motion.div>
  );
}
