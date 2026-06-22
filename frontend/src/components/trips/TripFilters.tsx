import * as React from "react";
import { getOnayDurumMeta } from "../../lib/status-labels";
import { AnimatePresence, motion } from "framer-motion";
import {
  Bookmark,
  Calendar,
  Clock,
  Filter,
  FilterX,
  Save,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { preferenceService, Preference } from "../../api/preferences";
import { useTripStore } from "../../stores/use-trip-store";
import {
  TRIP_STATUS_IPTAL,
  TRIP_STATUS_PLANLANDI,
  TRIP_STATUS_TAMAMLANDI,
  type TripStatus,
  normalizeTripStatusOrEmpty,
} from "../../lib/trip-status";
import { cn } from "../../lib/utils";
import { DataExportImport } from "../shared/DataExportImport";
import { Button } from "../ui/Button";
import { useTripsResources } from "../../resources/useResources";

interface TripFiltersProps {
  onExport: () => Promise<void>;
  onImport: (file: File) => Promise<any>;
  onDownloadTemplate: () => Promise<void>;
  dataUpdatedAt?: number;
}

export const TripFilters: React.FC<TripFiltersProps> = ({
  onExport,
  onImport,
  onDownloadTemplate,
  dataUpdatedAt,
}) => {
  const { tripFilterText, tripModuleText } = useTripsResources();
  const STATUS_TABS: Array<{ label: string; value: TripStatus | "" }> = [
    { label: tripFilterText.tabs.all, value: "" },
    { label: tripFilterText.tabs.planned, value: TRIP_STATUS_PLANLANDI },
    { label: tripFilterText.tabs.completed, value: TRIP_STATUS_TAMAMLANDI },
    { label: tripFilterText.tabs.canceled, value: TRIP_STATUS_IPTAL },
  ];
  const { filters, setFilters, resetFilters } = useTripStore();
  const [isOpen, setIsOpen] = React.useState(false);
  const [secondsAgo, setSecondsAgo] = React.useState(0);

  React.useEffect(() => {
    if (!dataUpdatedAt) return;
    const update = () =>
      setSecondsAgo(Math.floor((Date.now() - dataUpdatedAt) / 1000));
    update();
    const timer = setInterval(update, 5000);
    return () => clearInterval(timer);
  }, [dataUpdatedAt]);

  const handleTodayFilter = () => {
    const today = new Date().toISOString().split("T")[0];
    setFilters({ baslangic_tarih: today, bitis_tarih: today });
  };
  const [savedFilters, setSavedFilters] = React.useState<Preference[]>([]);
  const [isSaving, setIsSaving] = React.useState(false);
  const [newFilterName, setNewFilterName] = React.useState("");
  const [showSaveInput, setShowSaveInput] = React.useState(false);

  const loadSavedFilters = async () => {
    try {
      const preferences = await preferenceService.getPreferences(
        "seferler",
        "filtre",
      );
      setSavedFilters(preferences);
    } catch (error) {
      console.error("Failed to load saved trip filters", error);
    }
  };

  React.useEffect(() => {
    loadSavedFilters();
  }, []);

  const handleSaveFilter = async () => {
    if (!newFilterName.trim()) {
      toast.error(tripFilterText.saveNameRequired);
      return;
    }

    setIsSaving(true);

    try {
      await preferenceService.savePreference({
        modul: "seferler",
        ayar_tipi: "filtre",
        ad: newFilterName,
        deger: filters,
        is_default: false,
      });
      toast.success(tripFilterText.saveSuccess);
      setNewFilterName("");
      setShowSaveInput(false);
      loadSavedFilters();
    } catch {
      toast.error(tripFilterText.saveError);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteFilter = async (
    preferenceId: number,
    event: React.MouseEvent,
  ) => {
    event.stopPropagation();
    try {
      await preferenceService.deletePreference(preferenceId);
      toast.success(tripFilterText.deleteSuccess);
      loadSavedFilters();
    } catch {
      toast.error(tripFilterText.deleteError);
    }
  };

  const hasActiveFilters = Boolean(
    filters.durum ||
      filters.onay_durumu ||
      filters.search ||
      filters.baslangic_tarih ||
      filters.bitis_tarih ||
      filters.arac_id ||
      filters.sofor_id,
  );
  const selectedStatus = normalizeTripStatusOrEmpty(filters.durum);

  return (
    <div className="mb-6 flex flex-col items-center justify-between gap-4 md:flex-row">
      <div className="flex w-full items-center gap-3 md:w-auto">
        <div className="relative flex-1 md:w-80">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-tertiary" />
          <input
            type="text"
            placeholder={tripFilterText.searchPlaceholder}
            value={filters.search || ""}
            onChange={(event) => setFilters({ search: event.target.value })}
            className="h-11 w-full rounded-xl border border-border bg-surface pl-10 pr-4 text-sm outline-none transition-all focus:border-accent/40"
          />
        </div>
        <Button
          variant="secondary"
          onClick={() => setIsOpen(true)}
          className={cn(
            "flex h-11 items-center gap-2 rounded-xl px-5 text-xs font-bold uppercase tracking-widest transition-all",
            hasActiveFilters
              ? "border-accent/20 bg-accent/10 text-accent"
              : "border-border bg-surface text-secondary",
          )}
        >
          <Filter size={16} />
          {tripFilterText.openFilters}
          {hasActiveFilters && (
            <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />
          )}
        </Button>
        <Button
          variant="secondary"
          onClick={handleTodayFilter}
          className="flex h-11 items-center gap-2 rounded-xl border-border bg-surface px-4 text-xs font-bold uppercase tracking-widest text-secondary transition-all hover:border-accent/30 hover:text-accent"
        >
          <Calendar size={14} />
          {tripFilterText.todayFilter}
        </Button>
      </div>

      <div className="flex items-center gap-3">
        {dataUpdatedAt != null && secondsAgo >= 0 && (
          <span className="flex items-center gap-1.5 text-[10px] font-bold text-tertiary">
            <Clock size={11} className="opacity-50" />
            {tripModuleText.lastUpdated(secondsAgo)}
          </span>
        )}
        <DataExportImport
          onExport={onExport}
          onImport={onImport}
          onDownloadTemplate={onDownloadTemplate}
          variant="toolbar"
        />
      </div>

      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsOpen(false)}
              className="fixed inset-0 z-[100] bg-black/20 backdrop-blur-[2px]"
            />
            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 200 }}
              className="fixed right-0 top-0 z-[101] flex h-full w-full max-w-md flex-col border-l border-border bg-surface shadow-2xl"
            >
              <div className="flex items-center justify-between border-b border-border bg-elevated/20 p-6">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/5 text-accent">
                    <Filter size={20} />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-primary">
                      {tripFilterText.advancedFiltersTitle}
                    </h2>
                    <p className="text-[10px] font-black uppercase tracking-widest text-tertiary">
                      {tripFilterText.advancedFiltersDescription}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setIsOpen(false)}
                  className="rounded-xl p-2 transition-all hover:bg-elevated"
                >
                  <X size={20} className="text-secondary" />
                </button>
              </div>

              <div className="custom-scrollbar flex-1 space-y-8 overflow-y-auto p-6">
                <div className="space-y-3">
                  <label className="text-xs font-black uppercase tracking-[0.2em] text-tertiary">
                    {tripFilterText.statusLabel}
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {STATUS_TABS.map((tab) => (
                      <button
                        key={tab.value}
                        onClick={() => setFilters({ durum: tab.value })}
                        className={cn(
                          "group flex items-center justify-between rounded-xl border px-4 py-3 text-left text-xs font-bold transition-all",
                          selectedStatus === tab.value
                            ? "border-accent bg-accent text-white shadow-lg shadow-accent/20"
                            : "border-border bg-surface text-secondary hover:border-accent/40 hover:text-primary",
                        )}
                      >
                        {tab.label}
                        {selectedStatus === tab.value && (
                          <div className="h-1.5 w-1.5 rounded-full bg-white" />
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <label className="text-xs font-black uppercase tracking-[0.2em] text-tertiary">
                    Telegram Onay Durumu
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {(
                      [
                        { label: "Tümü", value: "" },
                        {
                          label: getOnayDurumMeta("beklemede").label,
                          value: "beklemede",
                        },
                        {
                          label: getOnayDurumMeta("onaylandi").label,
                          value: "onaylandi",
                        },
                        {
                          label: getOnayDurumMeta("reddedildi").label,
                          value: "reddedildi",
                        },
                      ] as const
                    ).map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() =>
                          setFilters({ onay_durumu: opt.value || undefined })
                        }
                        className={cn(
                          "group flex items-center justify-between rounded-xl border px-4 py-3 text-left text-xs font-bold transition-all",
                          (filters.onay_durumu ?? "") === opt.value
                            ? "border-warning bg-warning text-white shadow-lg shadow-warning/20"
                            : "border-border bg-surface text-secondary hover:border-warning/40 hover:text-primary",
                        )}
                      >
                        {opt.label}
                        {(filters.onay_durumu ?? "") === opt.value && (
                          <div className="h-1.5 w-1.5 rounded-full bg-white" />
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <label className="text-xs font-black uppercase tracking-[0.2em] text-tertiary">
                    {tripFilterText.dateRangeLabel}
                  </label>
                  <div className="space-y-3">
                    <div className="relative">
                      <Calendar className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-tertiary" />
                      <input
                        type="date"
                        value={filters.baslangic_tarih || ""}
                        onChange={(event) =>
                          setFilters({
                            baslangic_tarih: event.target.value,
                          })
                        }
                        className="h-12 w-full rounded-xl border border-border bg-elevated/30 pl-12 pr-4 text-sm outline-none transition-all focus:border-accent/40"
                      />
                    </div>
                    <div className="relative">
                      <Calendar className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-tertiary" />
                      <input
                        type="date"
                        value={filters.bitis_tarih || ""}
                        onChange={(event) =>
                          setFilters({
                            bitis_tarih: event.target.value,
                          })
                        }
                        className="h-12 w-full rounded-xl border border-border bg-elevated/30 pl-12 pr-4 text-sm outline-none transition-all focus:border-accent/40"
                      />
                    </div>
                  </div>
                </div>

                {savedFilters.length > 0 && (
                  <div className="space-y-3">
                    <label className="text-xs font-black uppercase tracking-[0.2em] text-tertiary">
                      {tripFilterText.savedFiltersLabel}
                    </label>
                    <div className="space-y-2">
                      {savedFilters.map((preference) => (
                        <div
                          key={preference.id}
                          className="group flex items-center gap-2"
                        >
                          <button
                            onClick={() => setFilters(preference.deger)}
                            className={cn(
                              "flex flex-1 items-center gap-3 rounded-xl border p-3 text-sm font-semibold transition-all",
                              JSON.stringify(filters) ===
                                JSON.stringify(preference.deger)
                                ? "border-accent bg-accent/5 text-accent"
                                : "border-border bg-surface text-secondary hover:bg-elevated/50",
                            )}
                          >
                            <Bookmark size={14} />
                            {preference.ad}
                          </button>
                          <button
                            onClick={(event) =>
                              handleDeleteFilter(preference.id, event)
                            }
                            className="rounded-xl p-3 text-tertiary transition-all hover:bg-danger/5 hover:text-danger"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="space-y-3 border-t border-border bg-elevated/10 p-6">
                <div className="flex gap-3">
                  <Button
                    variant="secondary"
                    onClick={() => {
                      resetFilters();
                      toast.success(tripFilterText.resetSuccess);
                    }}
                    className="h-12 flex-1 rounded-xl border-border text-xs font-bold uppercase tracking-widest"
                  >
                    <FilterX size={16} className="mr-2" />
                    {tripFilterText.reset}
                  </Button>
                  <Button
                    variant="primary"
                    onClick={() => setIsOpen(false)}
                    className="h-12 flex-[2] rounded-xl text-xs font-bold uppercase tracking-widest shadow-lg shadow-accent/20"
                  >
                    {tripFilterText.apply}
                  </Button>
                </div>

                <button
                  onClick={() => setShowSaveInput(true)}
                  className="w-full py-2 text-center text-[10px] font-black uppercase tracking-[0.2em] text-accent transition-all hover:opacity-80"
                >
                  {tripFilterText.saveCurrentFilter}
                </button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showSaveInput && (
          <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowSaveInput(false)}
              className="fixed inset-0 bg-black/40 backdrop-blur-sm"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              className="relative w-full max-w-sm overflow-hidden rounded-[24px] border border-border bg-surface p-6 shadow-2xl"
            >
              <div className="mb-6 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/5 text-accent">
                  <Save size={20} />
                </div>
                <h3 className="text-lg font-bold text-primary">
                  {tripFilterText.saveDialogTitle}
                </h3>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="mb-2 block px-1 text-[10px] font-black uppercase tracking-widest text-tertiary">
                    {tripFilterText.filterNameLabel}
                  </label>
                  <input
                    autoFocus
                    type="text"
                    placeholder={tripFilterText.filterNamePlaceholder}
                    value={newFilterName}
                    onChange={(event) => setNewFilterName(event.target.value)}
                    className="h-12 w-full rounded-xl border border-border bg-elevated/30 px-4 text-sm outline-none transition-all focus:border-accent/40"
                    onKeyDown={(event) =>
                      event.key === "Enter" && handleSaveFilter()
                    }
                  />
                </div>
                <div className="flex gap-3 pt-2">
                  <Button
                    variant="secondary"
                    onClick={() => setShowSaveInput(false)}
                    className="h-12 flex-1 rounded-xl text-xs font-bold uppercase tracking-widest"
                  >
                    {tripFilterText.cancel}
                  </Button>
                  <Button
                    variant="primary"
                    onClick={handleSaveFilter}
                    isLoading={isSaving}
                    className="h-12 flex-[2] rounded-xl text-xs font-bold uppercase tracking-widest shadow-md shadow-accent/20"
                  >
                    {tripFilterText.save}
                  </Button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};
