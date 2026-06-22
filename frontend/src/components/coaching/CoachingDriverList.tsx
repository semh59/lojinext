import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Search, Star, User2 } from "lucide-react";
import { Card } from "../ui/Card";
import { driverService } from "../../api/drivers";
import type { Driver } from "../../types";
import { useDebounce } from "../../hooks/useDebounce";
import { cn } from "../../lib/utils";
import {
  coachingDriverListText,
  coachingPageText,
} from "../../resources/tr/coaching";

interface CoachingDriverListProps {
  selectedDriverId: number | null;
  onSelect: (driver: Driver) => void;
}

export function CoachingDriverList({
  selectedDriverId,
  onSelect,
}: CoachingDriverListProps) {
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["coaching", "drivers", debouncedSearch],
    queryFn: () =>
      driverService.getAll({
        aktif_only: true,
        limit: 200,
        search: debouncedSearch || undefined,
      }),
    staleTime: 5 * 60 * 1000,
  });

  const drivers = useMemo(() => data?.items ?? [], [data?.items]);

  return (
    <Card
      padding="md"
      className="flex flex-col gap-3 h-full max-h-[calc(100vh-200px)]"
    >
      <div className="flex items-center gap-2">
        <User2 className="h-4 w-4 text-accent" />
        <h2 className="text-sm font-semibold text-primary">
          {coachingDriverListText.heading}
        </h2>
        {drivers.length > 0 && (
          <span className="text-xs text-secondary">({drivers.length})</span>
        )}
      </div>

      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-secondary" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={coachingDriverListText.searchPlaceholder}
          className="input-base !pl-7 !h-8 text-xs"
          aria-label={coachingDriverListText.searchPlaceholder}
        />
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-1.5">
        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-6 text-secondary text-xs">
            <Loader2 className="h-4 w-4 animate-spin" />
          </div>
        ) : isError ? (
          <p className="text-xs text-danger px-2 py-3">Şoförler yüklenemedi</p>
        ) : drivers.length === 0 ? (
          <p className="text-xs text-secondary px-2 py-3">
            {coachingPageText.emptyDriverList}
          </p>
        ) : (
          drivers.map((driver) => (
            <button
              key={driver.id}
              type="button"
              onClick={() => onSelect(driver)}
              className={cn(
                "flex w-full items-center gap-3 rounded-card px-3 py-2 text-left transition-colors",
                selectedDriverId === driver.id
                  ? "bg-accent/10 border border-accent/30"
                  : "hover:bg-elevated border border-transparent",
              )}
            >
              <div
                className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-card border text-xs font-bold",
                  selectedDriverId === driver.id
                    ? "border-accent/40 bg-accent/20 text-accent"
                    : "border-border bg-elevated text-secondary",
                )}
              >
                {driver.ad_soyad[0]}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-semibold text-primary">
                  {driver.ad_soyad}
                </p>
                <div className="flex items-center gap-1.5 text-[10px] text-secondary">
                  <Star className="h-2.5 w-2.5 text-warning fill-warning" />
                  {driver.score?.toFixed(2) ?? "—"}
                </div>
              </div>
            </button>
          ))
        )}
      </div>
    </Card>
  );
}
