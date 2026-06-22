import { LayoutGrid, LayoutList, Search } from "lucide-react";

import { cn } from "../../lib/utils";
import { Input } from "../ui/Input";
import { useDriversResources } from "../../resources/useResources";

interface DriverFiltersProps {
  search: string;
  setSearch: (value: string) => void;
  viewMode: "table" | "grid";
  setViewMode: (value: "table" | "grid") => void;
  aktifOnly: boolean;
  setAktifOnly: (value: boolean) => void;
  ehliyetFilter: string;
  setEhliyetFilter: (value: string) => void;
  ehliyetOptions: string[];
  minScore: number;
  setMinScore: (value: number) => void;
  maxScore: number;
  setMaxScore: (value: number) => void;
}

const SCORE_MIN = 0.1;
const SCORE_MAX = 2.0;
const SCORE_STEP = 0.1;

function clampScore(value: number, min: number, max: number): number {
  if (Number.isNaN(value)) return min;
  return Math.min(Math.max(value, min), max);
}

export function DriverFilters({
  search,
  setSearch,
  viewMode,
  setViewMode,
  aktifOnly,
  setAktifOnly,
  ehliyetFilter,
  setEhliyetFilter,
  ehliyetOptions,
  minScore,
  setMinScore,
  maxScore,
  setMaxScore,
}: DriverFiltersProps) {
  const { driverFilterText } = useDriversResources();
  const handleReset = () => {
    setSearch("");
    setEhliyetFilter("");
    setAktifOnly(true);
    setMinScore(SCORE_MIN);
    setMaxScore(SCORE_MAX);
  };

  const handleMinScoreChange = (raw: number) => {
    const clamped = clampScore(raw, SCORE_MIN, SCORE_MAX);
    // Min, max'tan büyük olamaz.
    setMinScore(Math.min(clamped, maxScore));
  };

  const handleMaxScoreChange = (raw: number) => {
    const clamped = clampScore(raw, SCORE_MIN, SCORE_MAX);
    // Max, min'den küçük olamaz.
    setMaxScore(Math.max(clamped, minScore));
  };

  return (
    <div className="mb-8 rounded-[12px] border border-border bg-surface p-6 shadow-sm">
      <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-center">
        <div className="flex flex-1 flex-col items-stretch gap-4 sm:flex-row sm:items-center">
          <div className="relative max-w-sm flex-1">
            <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-secondary transition-colors group-focus-within:text-accent" />
            <Input
              placeholder={driverFilterText.searchPlaceholder}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="h-10 rounded-[8px] border-transparent bg-elevated pl-10 text-primary placeholder:text-secondary transition-all focus:border-border focus:bg-surface"
            />
          </div>

          <div className="flex items-center gap-1.5 rounded-[10px] border border-border/50 bg-elevated p-1">
            <button
              onClick={() => setViewMode("table")}
              className={cn(
                "flex h-8 items-center gap-2 rounded-[6px] px-3 text-[11px] font-bold transition-all",
                viewMode === "table"
                  ? "border border-border/50 bg-surface text-accent shadow-sm"
                  : "text-secondary hover:text-primary",
              )}
            >
              <LayoutList className="h-3.5 w-3.5" />
              {driverFilterText.views.table}
            </button>
            <button
              onClick={() => setViewMode("grid")}
              className={cn(
                "flex h-8 items-center gap-2 rounded-[6px] px-3 text-[11px] font-bold transition-all",
                viewMode === "grid"
                  ? "border border-border/50 bg-surface text-accent shadow-sm"
                  : "text-secondary hover:text-primary",
              )}
            >
              <LayoutGrid className="h-3.5 w-3.5" />
              {driverFilterText.views.grid}
            </button>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={() => setAktifOnly(!aktifOnly)}
            className={cn(
              "flex h-10 items-center gap-2 rounded-[8px] border px-4 text-xs font-bold transition-all",
              aktifOnly
                ? "border-success/20 bg-success/10 text-success"
                : "border-border bg-elevated text-secondary hover:border-secondary",
            )}
          >
            <div
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                aktifOnly
                  ? "bg-success shadow-[0_0_8px_rgba(34,197,94,0.4)]"
                  : "bg-border",
              )}
            />
            {driverFilterText.activeOnly}
          </button>

          <select
            value={ehliyetFilter}
            onChange={(event) => setEhliyetFilter(event.target.value)}
            className="h-10 rounded-[8px] border border-border bg-elevated px-4 text-xs font-bold text-primary outline-none transition-all focus:border-secondary"
          >
            <option value="">{driverFilterText.allLicenses}</option>
            {ehliyetOptions
              .filter((option) => option)
              .map((option) => (
                <option key={option} value={option}>
                  {driverFilterText.licenseSuffix(option)}
                </option>
              ))}
          </select>

          <button
            onClick={handleReset}
            className="h-10 px-4 text-xs font-bold text-secondary transition-colors hover:text-primary"
          >
            {driverFilterText.reset}
          </button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-4 border-t border-border/50 pt-4">
        <span className="text-[11px] font-bold uppercase tracking-wider text-secondary">
          {driverFilterText.scoreRange}
        </span>
        <label className="flex items-center gap-2 text-xs text-secondary">
          {driverFilterText.minScore}
          <input
            type="number"
            min={SCORE_MIN}
            max={SCORE_MAX}
            step={SCORE_STEP}
            value={minScore.toFixed(1)}
            onChange={(e) => handleMinScoreChange(Number(e.target.value))}
            className="h-8 w-16 rounded-[6px] border border-border bg-elevated px-2 text-xs font-semibold text-primary outline-none focus:border-secondary"
            aria-label={driverFilterText.minScore}
          />
        </label>
        <input
          type="range"
          min={SCORE_MIN}
          max={SCORE_MAX}
          step={SCORE_STEP}
          value={minScore}
          onChange={(e) => handleMinScoreChange(Number(e.target.value))}
          className="h-2 w-24 cursor-pointer accent-accent"
          aria-label={`${driverFilterText.minScore} ${driverFilterText.scoreRange}`}
        />
        <input
          type="range"
          min={SCORE_MIN}
          max={SCORE_MAX}
          step={SCORE_STEP}
          value={maxScore}
          onChange={(e) => handleMaxScoreChange(Number(e.target.value))}
          className="h-2 w-24 cursor-pointer accent-accent"
          aria-label={`${driverFilterText.maxScore} ${driverFilterText.scoreRange}`}
        />
        <label className="flex items-center gap-2 text-xs text-secondary">
          {driverFilterText.maxScore}
          <input
            type="number"
            min={SCORE_MIN}
            max={SCORE_MAX}
            step={SCORE_STEP}
            value={maxScore.toFixed(1)}
            onChange={(e) => handleMaxScoreChange(Number(e.target.value))}
            className="h-8 w-16 rounded-[6px] border border-border bg-elevated px-2 text-xs font-semibold text-primary outline-none focus:border-secondary"
            aria-label={driverFilterText.maxScore}
          />
        </label>
      </div>
    </div>
  );
}
