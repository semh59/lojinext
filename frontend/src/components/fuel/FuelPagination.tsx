import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";

import { cn } from "../../lib/utils";
import { useFuelResources } from "../../resources/useResources";

interface FuelPaginationProps {
  currentPage: number;
  totalCount: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}

export function FuelPagination({
  currentPage,
  totalCount,
  pageSize,
  onPageChange,
}: FuelPaginationProps) {
  const { fuelPaginationText } = useFuelResources();
  const totalPages = Math.ceil(totalCount / pageSize);

  if (totalPages <= 1) return null;

  const renderPageNumbers = () => {
    const pages: Array<number | string> = [];
    const showEllipsis = totalPages > 7;

    if (!showEllipsis) {
      for (let page = 1; page <= totalPages; page += 1) {
        pages.push(page);
      }
    } else if (currentPage <= 4) {
      pages.push(1, 2, 3, 4, 5, "...", totalPages);
    } else if (currentPage >= totalPages - 3) {
      pages.push(
        1,
        "...",
        totalPages - 4,
        totalPages - 3,
        totalPages - 2,
        totalPages - 1,
        totalPages,
      );
    } else {
      pages.push(
        1,
        "...",
        currentPage - 1,
        currentPage,
        currentPage + 1,
        "...",
        totalPages,
      );
    }

    return pages.map((page, index) => (
      <button
        key={`${page}-${index}`}
        disabled={page === "..."}
        onClick={() => typeof page === "number" && onPageChange(page)}
        className={cn(
          "flex h-9 w-9 items-center justify-center rounded-lg text-xs font-bold transition-all",
          page === currentPage
            ? "bg-accent text-bg-base shadow-sm"
            : page === "..."
              ? "cursor-default text-secondary"
              : "border border-transparent text-secondary hover:border-border hover:bg-elevated",
        )}
      >
        {page}
      </button>
    ));
  };

  return (
    <div className="flex flex-col items-center justify-between gap-4 border-t border-border bg-elevated/30 px-6 py-4 backdrop-blur-sm sm:flex-row">
      <div className="text-[10px] font-bold uppercase tracking-widest text-secondary">
        {fuelPaginationText.totalRecords(totalCount)}
      </div>

      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(1)}
          disabled={currentPage === 1}
          className="hidden items-center justify-center rounded-xl p-2.5 font-black text-secondary transition-all hover:bg-surface disabled:opacity-30 sm:flex"
          title={fuelPaginationText.firstPage}
          aria-label={fuelPaginationText.firstPage}
        >
          <ChevronsLeft className="h-4.5 w-4.5" />
        </button>
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          className="flex items-center gap-1 rounded-xl px-3 py-2.5 text-sm font-medium text-secondary transition-all hover:bg-surface disabled:opacity-30"
          aria-label={fuelPaginationText.previous}
        >
          <ChevronLeft className="h-4.5 w-4.5" />
          {fuelPaginationText.previous}
        </button>

        <div className="mx-2 flex items-center gap-1">
          {renderPageNumbers()}
        </div>

        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          className="flex items-center gap-1 rounded-xl px-3 py-2.5 text-sm font-medium text-secondary transition-all hover:bg-surface disabled:opacity-30"
          aria-label={fuelPaginationText.next}
        >
          {fuelPaginationText.next}
          <ChevronRight className="h-4.5 w-4.5" />
        </button>
        <button
          onClick={() => onPageChange(totalPages)}
          disabled={currentPage === totalPages}
          className="hidden items-center justify-center rounded-xl p-2.5 text-secondary transition-all hover:bg-surface disabled:opacity-30 sm:flex"
          title={fuelPaginationText.lastPage}
          aria-label={fuelPaginationText.lastPage}
        >
          <ChevronsRight className="h-4.5 w-4.5" />
        </button>
      </div>

      <div className="text-xs font-bold uppercase tracking-widest text-secondary sm:text-right">
        {fuelPaginationText.pageSummary(currentPage, totalPages)}
      </div>
    </div>
  );
}
