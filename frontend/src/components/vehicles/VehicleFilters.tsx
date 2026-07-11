import { AnimatePresence, motion } from "framer-motion";
import { Filter, Search } from "lucide-react";

import { cn } from "../../lib/utils";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { useVehiclesResources } from "../../resources/useResources";

interface VehicleFiltersProps {
  search: string;
  setSearch: (value: string) => void;
  showOnlyActive: boolean;
  setShowOnlyActive: (value: boolean) => void;
  isFilterOpen: boolean;
  setIsFilterOpen: (value: boolean) => void;
  filters: {
    marka: string;
    model: string;
    min_yil: string;
    max_yil: string;
  };
  setFilters: (value: any) => void;
}

export function VehicleFilters({
  search,
  setSearch,
  showOnlyActive,
  setShowOnlyActive,
  isFilterOpen,
  setIsFilterOpen,
  filters,
  setFilters,
}: VehicleFiltersProps) {
  const { vehicleFilterText } = useVehiclesResources();
  const handleReset = () => {
    setFilters({ marka: "", model: "", min_yil: "", max_yil: "" });
    setSearch("");
  };

  const handleApplyFilters = () => setIsFilterOpen(false);

  return (
    <div className="mb-4 w-full rounded-[10px] border border-border bg-surface p-4 shadow-sm">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div className="relative max-w-sm flex-1">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-secondary" />
          <Input
            placeholder={vehicleFilterText.searchPlaceholder}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="pl-10"
          />
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowOnlyActive(!showOnlyActive)}
            className={cn(
              "flex h-[40px] items-center gap-2 rounded-[6px] border px-4 text-xs font-bold transition-all",
              showOnlyActive
                ? "border-success/20 bg-success/10 text-success"
                : "border-border bg-surface text-secondary hover:bg-elevated",
            )}
          >
            <div
              className={cn(
                "h-2 w-2 rounded-full",
                showOnlyActive
                  ? "bg-success shadow-[0_0_8px_rgba(34,197,94,0.3)]"
                  : "bg-border",
              )}
            />
            {vehicleFilterText.activeOnly}
          </button>

          <button
            onClick={() => setIsFilterOpen(!isFilterOpen)}
            className={cn(
              "flex h-[40px] items-center gap-2 rounded-[6px] border px-4 text-xs font-bold transition-all",
              isFilterOpen
                ? "border-accent/20 bg-accent/10 text-accent"
                : "border-border bg-surface text-secondary hover:bg-elevated hover:text-primary",
            )}
          >
            <Filter className="h-4 w-4" />
            {vehicleFilterText.advancedFilters}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {isFilterOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="mt-4 grid grid-cols-1 gap-4 border-t border-border pt-4 sm:grid-cols-2 lg:grid-cols-4"
          >
            <div className="space-y-1.5">
              <label className="pl-1 text-[10px] font-bold uppercase tracking-widest text-secondary">
                {vehicleFilterText.fields.brand}
              </label>
              <Input
                placeholder={vehicleFilterText.placeholders.brand}
                value={filters.marka}
                onChange={(event) =>
                  setFilters({ ...filters, marka: event.target.value })
                }
                className="h-10 rounded-xl border-border bg-elevated text-primary placeholder:text-secondary"
              />
            </div>
            <div className="space-y-1.5">
              <label className="pl-1 text-[10px] font-bold uppercase tracking-widest text-secondary">
                {vehicleFilterText.fields.model}
              </label>
              <Input
                placeholder={vehicleFilterText.placeholders.model}
                value={filters.model}
                onChange={(event) =>
                  setFilters({ ...filters, model: event.target.value })
                }
                className="h-10 rounded-xl border-border bg-elevated text-primary placeholder:text-secondary"
              />
            </div>
            <div className="space-y-1.5">
              <label className="pl-1 text-[10px] font-bold uppercase tracking-widest text-secondary">
                {vehicleFilterText.fields.minYear}
              </label>
              <Input
                type="number"
                placeholder={vehicleFilterText.placeholders.minYear}
                value={filters.min_yil}
                onChange={(event) =>
                  setFilters({ ...filters, min_yil: event.target.value })
                }
                className="h-10 rounded-xl border-border bg-elevated text-primary placeholder:text-secondary"
              />
            </div>
            <div className="space-y-1.5">
              <label className="pl-1 text-[10px] font-bold uppercase tracking-widest text-secondary">
                {vehicleFilterText.fields.maxYear}
              </label>
              <Input
                type="number"
                placeholder={vehicleFilterText.placeholders.maxYear}
                value={filters.max_yil}
                onChange={(event) =>
                  setFilters({ ...filters, max_yil: event.target.value })
                }
                className="h-10 rounded-xl border-border bg-elevated text-primary placeholder:text-secondary"
              />
            </div>
            <div className="col-span-full mt-2 flex justify-end gap-2">
              <Button
                variant="ghost"
                onClick={handleReset}
                className="text-secondary hover:text-primary"
              >
                {vehicleFilterText.reset}
              </Button>
              <Button variant="primary" onClick={handleApplyFilters}>
                {vehicleFilterText.apply}
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
