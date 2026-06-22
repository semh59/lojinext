import { AnimatePresence, motion } from "framer-motion";
import { Filter, LayoutGrid, List, Search } from "lucide-react";

import { trailerFilterText } from "../../resources/tr/trailers";
import { cn } from "../../lib/utils";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";

interface TrailerFiltersProps {
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
  viewMode: "grid" | "list";
  setViewMode: (value: "grid" | "list") => void;
}

export function TrailerFilters({
  search,
  setSearch,
  showOnlyActive,
  setShowOnlyActive,
  isFilterOpen,
  setIsFilterOpen,
  filters,
  setFilters,
  viewMode,
  setViewMode,
}: TrailerFiltersProps) {
  const handleReset = () => {
    setFilters({ marka: "", model: "", min_yil: "", max_yil: "" });
    setSearch("");
  };

  const handleApplyFilters = () => setIsFilterOpen(false);

  return (
    <div className="mb-4 w-full rounded-xl border border-border bg-surface/60 p-4 shadow-sm backdrop-blur-md">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div className="relative max-w-sm flex-1">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-accent/60" />
          <Input
            placeholder={trailerFilterText.searchPlaceholder}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="h-11 rounded-xl border-border bg-elevated pl-10 text-primary placeholder:text-secondary focus:border-accent focus:ring-accent/20"
          />
        </div>

        <div className="flex items-center gap-3">
          <div className="mr-2 flex rounded-xl border border-border bg-elevated p-1">
            <button
              onClick={() => setViewMode("grid")}
              className={cn(
                "rounded-lg p-2 transition-all",
                viewMode === "grid"
                  ? "bg-accent/20 text-accent shadow-lg shadow-accent/5"
                  : "text-secondary hover:bg-elevated hover:text-primary",
              )}
              title={trailerFilterText.titles.gridView}
            >
              <LayoutGrid className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode("list")}
              className={cn(
                "rounded-lg p-2 transition-all",
                viewMode === "list"
                  ? "bg-accent/20 text-accent shadow-lg shadow-accent/5"
                  : "text-secondary hover:bg-elevated hover:text-primary",
              )}
              title={trailerFilterText.titles.listView}
            >
              <List className="h-4 w-4" />
            </button>
          </div>

          <button
            onClick={() => setShowOnlyActive(!showOnlyActive)}
            className={cn(
              "flex h-11 items-center gap-2 rounded-xl border px-4 text-xs font-bold transition-all",
              showOnlyActive
                ? "border-success/20 bg-success/10 text-success shadow-lg shadow-success/5"
                : "border-border bg-elevated text-secondary hover:bg-surface",
            )}
          >
            <div
              className={cn(
                "h-2 w-2 rounded-full",
                showOnlyActive
                  ? "bg-success shadow-[0_0_5px_var(--success)]"
                  : "bg-border/40",
              )}
            />
            {trailerFilterText.titles.activeOnly}
          </button>

          <button
            onClick={() => setIsFilterOpen(!isFilterOpen)}
            className={cn(
              "flex h-11 items-center gap-2 rounded-xl border px-4 text-xs font-bold transition-all",
              isFilterOpen
                ? "border-accent/50 bg-accent/20 text-primary shadow-lg shadow-accent/5"
                : "border-border bg-elevated text-secondary hover:bg-surface hover:text-primary",
            )}
          >
            <Filter className="h-4 w-4" />
            {trailerFilterText.titles.advancedFilters}
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
              <label className="pl-1 text-[10px] font-bold uppercase tracking-widest text-accent/80">
                {trailerFilterText.fields.brand}
              </label>
              <Input
                placeholder={trailerFilterText.placeholders.brand}
                value={filters.marka}
                onChange={(event) =>
                  setFilters((current: any) => ({
                    ...current,
                    marka: event.target.value,
                  }))
                }
                className="h-10 rounded-xl border-accent/30 bg-elevated/40 text-primary placeholder:text-secondary"
              />
            </div>
            <div className="space-y-1.5">
              <label className="pl-1 text-[10px] font-bold uppercase tracking-widest text-accent/80">
                {trailerFilterText.fields.model}
              </label>
              <Input
                placeholder={trailerFilterText.placeholders.model}
                value={filters.model}
                onChange={(event) =>
                  setFilters((current: any) => ({
                    ...current,
                    model: event.target.value,
                  }))
                }
                className="h-10 rounded-xl border-border bg-elevated text-primary placeholder:text-secondary"
              />
            </div>
            <div className="space-y-1.5">
              <label className="pl-1 text-[10px] font-bold uppercase tracking-widest text-accent/80">
                {trailerFilterText.fields.minYear}
              </label>
              <Input
                type="number"
                placeholder={trailerFilterText.placeholders.minYear}
                value={filters.min_yil}
                onChange={(event) =>
                  setFilters((current: any) => ({
                    ...current,
                    min_yil: event.target.value,
                  }))
                }
                className="h-10 rounded-xl border-accent/30 bg-elevated/40 text-primary placeholder:text-secondary"
              />
            </div>
            <div className="space-y-1.5">
              <label className="pl-1 text-[10px] font-bold uppercase tracking-widest text-accent/80">
                {trailerFilterText.fields.maxYear}
              </label>
              <Input
                type="number"
                placeholder={trailerFilterText.placeholders.maxYear}
                value={filters.max_yil}
                onChange={(event) =>
                  setFilters((current: any) => ({
                    ...current,
                    max_yil: event.target.value,
                  }))
                }
                className="h-10 rounded-xl border-accent/30 bg-elevated/40 text-primary placeholder:text-secondary"
              />
            </div>
            <div className="col-span-full mt-2 flex justify-end gap-2">
              <Button
                variant="ghost"
                onClick={handleReset}
                className="text-secondary hover:text-primary"
              >
                {trailerFilterText.reset}
              </Button>
              <Button variant="primary" onClick={handleApplyFilters}>
                {trailerFilterText.apply}
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
