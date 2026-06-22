import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { dorseService } from "../../services/dorseService";
import { TrailerHeader } from "../trailers/TrailerHeader";
import { TrailerTable } from "../trailers/TrailerTable";
import { TrailerFilters } from "../trailers/TrailerFilters";
import { TrailerModal } from "../trailers/TrailerModal";
import TrailerDetailModal from "../trailers/TrailerDetailModal";
import TrailerDeleteModal from "../trailers/TrailerDeleteModal";
import { Dorse } from "../../types";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { cn } from "../../lib/utils";
import { useUrlState } from "../../hooks/use-url-state";
import { useTrailersResources } from "../../resources/useResources";
const ITEMS_PER_PAGE = 8;

export function TrailersModule() {
  const { trailerModuleText } = useTrailersResources();
  const queryClient = useQueryClient();
  // URL State (Synced filters)
  const [urlState, setUrlState] = useUrlState({
    view: "grid" as "grid" | "list",
    search: "",
    aktif: true as boolean,
    page: 1,
    marka: "",
    model: "",
    min_yil: "",
    max_yil: "",
  });

  const {
    view: viewMode,
    search,
    aktif: showOnlyActive,
    page: currentPage,
    marka,
    model,
    min_yil,
    max_yil,
  } = urlState;

  const filters = { marka, model, min_yil, max_yil };
  const [isFilterOpen, setIsFilterOpen] = useState(false);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [selectedTrailer, setSelectedTrailer] = useState<Dorse | null>(null);

  const { data: trailers = [], isLoading } = useQuery({
    queryKey: ["trailers", search, showOnlyActive, filters],
    queryFn: () =>
      dorseService.getAll({
        search,
        aktif_only: showOnlyActive,
        marka: filters.marka,
        model: filters.model,
        min_yil: filters.min_yil ? parseInt(filters.min_yil) : undefined,
        max_yil: filters.max_yil ? parseInt(filters.max_yil) : undefined,
      }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => dorseService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trailers"] });
      setIsDeleteOpen(false);
      setSelectedTrailer(null);
      toast.success(trailerModuleText.notifications.deleteSuccess);
    },
  });

  const handleEdit = (trailer: Dorse) => {
    setSelectedTrailer(trailer);
    setIsModalOpen(true);
  };

  const handleDelete = (trailer: Dorse) => {
    setSelectedTrailer(trailer);
    setIsDeleteOpen(true);
  };

  const handleViewDetail = (trailer: Dorse) => {
    setSelectedTrailer(trailer);
    setIsDetailOpen(true);
  };

  const handleImport = async (file: File) => {
    try {
      const res = await dorseService.uploadExcel(file);
      queryClient.invalidateQueries({ queryKey: ["trailers"] });
      toast.success(trailerModuleText.notifications.importSuccess);
      return res;
    } catch (error) {
      console.error("Import error:", error);
      toast.error(trailerModuleText.notifications.importError);
      throw error;
    }
  };

  // Pagination logic
  const totalPages = Math.ceil(trailers.length / ITEMS_PER_PAGE);
  const paginatedTrailers = trailers.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE,
  );

  return (
    <div className="space-y-6">
      <TrailerHeader
        onAdd={() => {
          setSelectedTrailer(null);
          setIsModalOpen(true);
        }}
        onImport={handleImport as any}
        onExport={() => dorseService.exportExcel()}
        onDownloadTemplate={() => dorseService.downloadTemplate()}
      />

      <div className="bg-surface rounded-[12px] border border-border p-8 shadow-sm relative overflow-hidden group">
        <TrailerFilters
          search={search}
          setSearch={(val) => setUrlState({ search: val, page: 1 })}
          showOnlyActive={showOnlyActive}
          setShowOnlyActive={(val) => setUrlState({ aktif: val, page: 1 })}
          isFilterOpen={isFilterOpen}
          setIsFilterOpen={setIsFilterOpen}
          filters={filters}
          setFilters={(newFilters: any) =>
            setUrlState({ ...newFilters, page: 1 })
          }
          viewMode={viewMode}
          setViewMode={(val) => setUrlState({ view: val })}
        />

        <div className="mt-8 min-h-[400px]">
          <TrailerTable
            trailers={paginatedTrailers}
            onEdit={handleEdit}
            onDelete={handleDelete}
            onViewDetail={handleViewDetail}
            loading={isLoading}
            viewMode={viewMode}
          />
        </div>

        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="mt-12 flex justify-center items-center gap-2">
            <button
              onClick={() =>
                setUrlState({ page: Math.max(1, currentPage - 1) })
              }
              disabled={currentPage === 1}
              className="h-10 px-4 rounded-[8px] bg-elevated text-primary border border-border disabled:opacity-30 hover:border-secondary transition-all font-bold text-xs flex items-center gap-2"
            >
              <ChevronLeft className="w-4 h-4" />
              {trailerModuleText.pagination.previous}
            </button>

            <div className="flex items-center gap-1.5 mx-2">
              {Array.from({ length: totalPages }, (_, i) => i + 1).map(
                (page) => (
                  <button
                    key={page}
                    onClick={() => setUrlState({ page })}
                    className={cn(
                      "w-10 h-10 rounded-[8px] font-bold text-xs transition-all border",
                      currentPage === page
                        ? "bg-accent/10 text-accent border-accent/20"
                        : "bg-surface text-secondary border-border hover:bg-elevated hover:text-primary",
                    )}
                  >
                    {page}
                  </button>
                ),
              )}
            </div>

            <button
              onClick={() =>
                setUrlState({ page: Math.min(totalPages, currentPage + 1) })
              }
              disabled={currentPage === totalPages}
              className="h-10 px-4 rounded-[8px] bg-elevated text-primary border border-border disabled:opacity-30 hover:border-secondary transition-all font-bold text-xs flex items-center gap-2"
            >
              {trailerModuleText.pagination.next}
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {isModalOpen && (
        <TrailerModal
          isOpen={isModalOpen}
          trailer={selectedTrailer}
          onClose={() => {
            setIsModalOpen(false);
            setSelectedTrailer(null);
          }}
          onSave={async (data) => {
            try {
              if (selectedTrailer?.id) {
                await dorseService.update(selectedTrailer.id, data);
                toast.success(trailerModuleText.notifications.updateSuccess);
              } else {
                await dorseService.create(data as Dorse);
                toast.success(trailerModuleText.notifications.createSuccess);
              }
              queryClient.invalidateQueries({ queryKey: ["trailers"] });
              setIsModalOpen(false);
            } catch (error: any) {
              console.error("Dorse save error:", error);
              toast.error(
                error.message || trailerModuleText.notifications.saveFallback,
              );
              throw error; // Rethrow to keep modal loading state if handled inside
            }
          }}
        />
      )}

      {isDetailOpen && (
        <TrailerDetailModal
          trailer={selectedTrailer}
          onClose={() => {
            setIsDetailOpen(false);
            setSelectedTrailer(null);
          }}
        />
      )}

      <TrailerDeleteModal
        trailer={selectedTrailer}
        isOpen={isDeleteOpen}
        onClose={() => {
          setIsDeleteOpen(false);
          setSelectedTrailer(null);
        }}
        onConfirm={() =>
          selectedTrailer?.id && deleteMutation.mutate(selectedTrailer.id)
        }
        isDeleting={deleteMutation.isPending}
      />
    </div>
  );
}
