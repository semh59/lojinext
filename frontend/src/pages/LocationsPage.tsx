import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  BarChart3,
  Clock,
  MapIcon,
  Plus,
  RefreshCw,
  Search,
  Zap,
} from "lucide-react";

import { AnalysisModal } from "../components/locations/AnalysisModal";
import { LocationFormModal } from "../components/locations/LocationFormModal";
import { LocationList } from "../components/locations/LocationList";
import { DataExportImport } from "../components/shared/DataExportImport";
import { Button } from "../components/ui/Button";
import { useLocationsPage } from "../hooks/useLocationsPage";
import { cn } from "../lib/utils";
import { locationsPageText } from "../resources/tr/locations";
import { locationService } from "../api/locations";

const buildKpis = (
  stats:
    | {
        total: number;
        analyzed: number;
        avg_distance_km: number;
        high_difficulty: number;
      }
    | undefined,
) => [
  {
    label: locationsPageText.kpis.totalRoutes.label,
    value: stats?.total ?? "—",
    hint: locationsPageText.kpis.totalRoutes.hint,
    icon: MapIcon,
    tone: "text-accent",
  },
  {
    label: locationsPageText.kpis.analyzedRoutes.label,
    value: stats ? `${stats.analyzed} / ${stats.total}` : "—",
    hint: locationsPageText.kpis.analyzedRoutes.hint,
    icon: BarChart3,
    tone: "text-info",
  },
  {
    label: locationsPageText.kpis.averageDistance.label,
    value: stats ? `${stats.avg_distance_km.toFixed(0)} km` : "—",
    hint: locationsPageText.kpis.averageDistance.hint,
    icon: RefreshCw,
    tone: "text-success",
  },
  {
    label: locationsPageText.kpis.highDifficulty.label,
    value: stats?.high_difficulty ?? "—",
    hint: locationsPageText.kpis.highDifficulty.hint,
    icon: AlertTriangle,
    tone: "text-danger",
  },
];

export default function LocationsPage() {
  const {
    search,
    zorlukFilter,
    page,
    setFilters,
    locations,
    totalCount,
    totalPages,
    isLoading,
    isFetching,
    refetch,
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
    handleAdd,
    handleEdit,
    handleAnalyze,
    handleDelete,
    handleSave,
    handleDownloadTemplate,
    handleExport,
    handleImport,
  } = useLocationsPage();

  const { data: statsData } = useQuery({
    queryKey: ["location-stats"],
    queryFn: locationService.getStats,
    staleTime: 1000 * 60 * 5,
  });

  const { data: staleData } = useQuery({
    queryKey: ["location-stale"],
    queryFn: () => locationService.getStale(90),
    staleTime: 1000 * 60 * 10,
  });

  const kpis = buildKpis(statsData);

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold text-primary">
            {locationsPageText.heading}
          </h1>
          <p className="text-sm text-secondary">
            {locationsPageText.description}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <DataExportImport
            variant="toolbar"
            onImport={handleImport}
            onExport={handleExport}
            onDownloadTemplate={handleDownloadTemplate}
          />
          <Button
            variant="primary"
            onClick={handleAdd}
            className="h-[42px] px-6 shadow-md shadow-accent/20"
          >
            <Plus size={18} className="mr-2" />
            <span>{locationsPageText.addRoute}</span>
          </Button>
        </div>
      </div>

      {staleData && staleData.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-start gap-3 rounded-card border border-warning/30 bg-warning/5 px-4 py-3"
        >
          <Clock className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-bold text-warning">
              {staleData.length} güzergahın analizi 90 günden eski veya hiç
              yapılmamış
            </p>
            <p className="mt-0.5 text-xs text-warning/70 truncate">
              {staleData
                .slice(0, 3)
                .map((r) => `${r.cikis_yeri} → ${r.varis_yeri}`)
                .join(" · ")}
              {staleData.length > 3 ? ` · +${staleData.length - 3} daha` : ""}
            </p>
          </div>
          <Zap className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning/50" />
        </motion.div>
      )}

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        {kpis.map((kpi) => (
          <div
            key={kpi.label}
            className="glass relative flex flex-col gap-1 overflow-hidden rounded-card border border-border p-5 shadow-sm"
          >
            <div className="absolute right-0 top-0 p-4 opacity-10">
              <kpi.icon className={cn("h-12 w-12", kpi.tone)} />
            </div>
            <p className="text-[11px] font-bold uppercase tracking-wider text-tertiary">
              {kpi.label}
            </p>
            <span className="text-2xl font-bold text-primary">{kpi.value}</span>
            <span className="text-xs font-medium text-secondary">
              {kpi.hint}
            </span>
          </div>
        ))}
      </div>

      <div className="glass rounded-modal border border-border p-6 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <h2 className="text-lg font-bold text-primary">
              {locationsPageText.visibility.title}
            </h2>
            <p className="mt-1 text-sm text-secondary">
              {locationsPageText.visibility.description}
            </p>
          </div>
          <div className="rounded-card border border-border/50 bg-elevated/30 px-4 py-3 text-sm text-secondary">
            {statsData
              ? locationsPageText.visibility.readyCount(statsData.analyzed)
              : locationsPageText.visibility.empty}
          </div>
        </div>
      </div>

      <div className="glass rounded-modal border border-border p-6 shadow-sm">
        <div className="mb-8 flex flex-col items-center gap-4 border-b border-border/50 pb-8 md:flex-row">
          <div className="group relative w-full flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-tertiary transition-colors group-focus-within:text-accent" />
            <input
              placeholder={locationsPageText.searchPlaceholder}
              className="h-11 w-full rounded-xl border-none bg-elevated/50 pl-10 pr-4 text-sm font-medium text-primary outline-none transition-all focus:ring-2 focus:ring-accent/10"
              value={search}
              onChange={(event) =>
                setFilters({ search: event.target.value, page: 1 })
              }
            />
          </div>

          <div className="flex w-full items-center gap-3 md:w-auto">
            <select
              className="h-11 rounded-xl border-none bg-elevated/50 px-4 text-xs font-bold uppercase tracking-tighter text-secondary outline-none focus:ring-2 focus:ring-accent/10"
              value={zorlukFilter}
              onChange={(event) =>
                setFilters({ zorluk: event.target.value, page: 1 })
              }
            >
              <option value="">
                {locationsPageText.difficultyPlaceholder}
              </option>
              <option value="Normal">
                {locationsPageText.difficultyOptions.normal}
              </option>
              <option value="Orta">
                {locationsPageText.difficultyOptions.medium}
              </option>
              <option value="Zor">
                {locationsPageText.difficultyOptions.hard}
              </option>
            </select>
            <button
              onClick={() => refetch()}
              className="group flex h-11 w-11 items-center justify-center rounded-xl bg-elevated/50 transition-all active:scale-95 hover:bg-accent/5"
            >
              <RefreshCw
                className={cn(
                  "h-4 w-4 text-tertiary transition-colors group-hover:text-accent",
                  isFetching && "animate-spin",
                )}
              />
            </button>
          </div>
        </div>

        <div className="min-h-[400px]">
          <AnimatePresence mode="wait">
            <motion.div
              key="table-view"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
            >
              <LocationList
                locations={locations}
                loading={isLoading}
                onEdit={handleEdit}
                onDelete={handleDelete}
                onAnalyze={handleAnalyze}
                onAdd={handleAdd}
                viewMode="table"
              />
            </motion.div>
          </AnimatePresence>

          {locations.length > 0 ? (
            <div className="mt-8 flex items-center justify-between">
              <p className="text-xs font-medium text-tertiary">
                {locationsPageText.pagination.summary(
                  totalCount,
                  locations.length,
                )}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setFilters({ page: Math.max(1, page - 1) })}
                  disabled={page === 1}
                  className="rounded-card bg-elevated/50 px-5 py-2 text-xs font-bold text-secondary transition-colors hover:bg-elevated hover:text-primary disabled:opacity-30"
                >
                  {locationsPageText.pagination.previous}
                </button>
                <button
                  onClick={() =>
                    setFilters({ page: Math.min(totalPages, page + 1) })
                  }
                  disabled={page >= totalPages}
                  className="rounded-card bg-elevated/50 px-5 py-2 text-xs font-bold text-secondary transition-colors hover:bg-elevated hover:text-primary disabled:opacity-30"
                >
                  {locationsPageText.pagination.next}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <LocationFormModal
        isOpen={isFormOpen}
        onClose={() => {
          setIsFormOpen(false);
          setSelectedLocation(null);
        }}
        onSave={handleSave}
        location={selectedLocation}
      />

      <AnalysisModal
        isOpen={isAnalysisOpen}
        onClose={() => {
          setIsAnalysisOpen(false);
          setAnalysisLocation(null);
        }}
        location={analysisLocation}
        analysisData={analysisData}
        isLoading={isAnalysisLoading}
        onAnalyze={() => analysisLocation && handleAnalyze(analysisLocation)}
      />
    </div>
  );
}
