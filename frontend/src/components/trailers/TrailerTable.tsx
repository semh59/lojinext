import { useEffect, useState } from "react";

import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  Calendar,
  Container,
  Disc,
  Edit2,
  Trash2,
  Weight,
} from "lucide-react";

import { Dorse } from "../../types";
import { cn } from "../../lib/utils";
import { useTrailersResources } from "../../resources/useResources";

interface TrailerTableProps {
  trailers: Dorse[];
  onEdit: (trailer: Dorse) => void;
  onDelete: (trailer: Dorse) => void | Promise<void>;
  onViewDetail: (trailer: Dorse) => void;
  loading: boolean;
  viewMode?: "grid" | "list";
}

export function TrailerTable({
  trailers,
  loading,
  onEdit,
  onDelete,
  onViewDetail,
  viewMode = "grid",
}: TrailerTableProps) {
  const { trailerTableText } = useTrailersResources();
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set());
  const [deletedIds, setDeletedIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    setDeletedIds(new Set());
    setDeletingIds(new Set());
  }, [trailers]);

  const handleOptimisticDelete = async (trailer: Dorse) => {
    if (!trailer.id) {
      return;
    }

    const id = trailer.id;
    setDeletedIds((previous) => new Set([...previous, id]));
    setDeletingIds((previous) => new Set([...previous, id]));

    try {
      await onDelete(trailer);
    } catch {
      setDeletedIds((previous) => {
        const next = new Set(previous);
        next.delete(id);
        return next;
      });
    } finally {
      setDeletingIds((previous) => {
        const next = new Set(previous);
        next.delete(id);
        return next;
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-accent border-t-transparent" />
      </div>
    );
  }

  if (trailers.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-[32px] border-2 border-border border-dashed bg-surface/40 p-16 text-center shadow-inner backdrop-blur-md">
        <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-2xl border border-accent/30 bg-accent/10 shadow-lg">
          <Container className="h-10 w-10 text-accent" />
        </div>
        <h3 className="mb-2 text-2xl font-black text-primary">
          {trailerTableText.emptyTitle}
        </h3>
        <p className="max-w-sm text-sm text-secondary">
          {trailerTableText.emptyDescription}
        </p>
      </div>
    );
  }

  const visibleTrailerCount = trailers.filter(
    (trailer) => !deletedIds.has(trailer.id!),
  ).length;

  return (
    <div className="w-full space-y-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-3 text-xl font-black text-primary">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-accent/40 bg-accent/20 text-accent shadow-lg">
            <Container className="h-5 w-5" />
          </div>
          {trailerTableText.title}
        </h2>
        <div className="rounded-xl border border-border bg-elevated px-4 py-2 text-sm font-bold text-secondary shadow-inner">
          {trailerTableText.totalCount(visibleTrailerCount)}
        </div>
      </div>

      {viewMode === "list" ? (
        <div className="overflow-hidden rounded-[24px] border border-border bg-surface/80 shadow-lg backdrop-blur-xl">
          <div className="custom-scrollbar overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-border bg-elevated/40">
                  <th className="p-5 text-xs font-black uppercase tracking-widest text-secondary">
                    {trailerTableText.columns.plateAndBrand}
                  </th>
                  <th className="p-5 text-xs font-black uppercase tracking-widest text-secondary">
                    {trailerTableText.columns.typeAndYear}
                  </th>
                  <th className="p-5 text-xs font-black uppercase tracking-widest text-secondary">
                    {trailerTableText.columns.technical}
                  </th>
                  <th className="p-5 text-xs font-black uppercase tracking-widest text-secondary">
                    {trailerTableText.columns.status}
                  </th>
                  <th className="p-5 text-right text-xs font-black uppercase tracking-widest text-secondary">
                    {trailerTableText.columns.actions}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <AnimatePresence>
                  {trailers
                    .filter(
                      (trailer) => trailer.id && !deletedIds.has(trailer.id),
                    )
                    .map((trailer, index) => (
                      <motion.tr
                        key={trailer.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        transition={{ duration: 0.2, delay: index * 0.05 }}
                        className={cn(
                          "group transition-colors hover:bg-accent/5",
                          trailer.id &&
                            deletingIds.has(trailer.id) &&
                            "pointer-events-none bg-danger/10 opacity-50 grayscale",
                        )}
                      >
                        <td className="p-5">
                          <div className="flex items-center gap-4">
                            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-border bg-elevated shadow-inner">
                              <Container className="h-5 w-5 text-primary transition-colors group-hover:text-accent" />
                            </div>
                            <div>
                              <div className="text-sm font-black tracking-widest text-primary">
                                {trailer.plaka}
                              </div>
                              <div className="text-xs uppercase tracking-wider text-secondary">
                                {trailer.marka ||
                                  trailerTableText.labels.unknownBrand}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="p-5">
                          <div className="text-sm font-bold text-primary">
                            {trailer.tipi}
                          </div>
                          <div className="text-xs text-secondary">
                            {trailer.yil || "-"}{" "}
                            {trailerTableText.labels.modelSuffix}
                          </div>
                        </td>
                        <td className="p-5">
                          <div className="flex gap-4 text-sm">
                            <div className="flex items-center gap-1.5 text-primary">
                              <Weight className="h-3.5 w-3.5 text-secondary" />
                              <span className="font-bold">
                                {trailer.bos_agirlik_kg?.toLocaleString(
                                  "tr-TR",
                                ) || "-"}{" "}
                                kg
                              </span>
                            </div>
                            <div className="flex items-center gap-1.5 text-primary">
                              <Disc className="h-3.5 w-3.5 text-secondary" />
                              <span className="font-bold">
                                {trailer.lastik_sayisi || "-"}{" "}
                                {trailerTableText.labels.tireCount}
                              </span>
                            </div>
                          </div>
                        </td>
                        <td className="p-5">
                          <span
                            className={cn(
                              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest",
                              trailer.aktif
                                ? "border-success/30 bg-success/10 text-success"
                                : "border-border bg-elevated text-secondary",
                            )}
                          >
                            <span
                              className={cn(
                                "h-2 w-2 rounded-full",
                                trailer.aktif ? "bg-success" : "bg-secondary",
                              )}
                            />
                            {trailer.aktif
                              ? trailerTableText.status.active
                              : trailerTableText.status.inactive}
                          </span>
                        </td>
                        <td className="p-5 text-right">
                          <div className="flex items-center justify-end gap-2 opacity-0 transition-opacity group-hover:opacity-100">
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                onViewDetail(trailer);
                              }}
                              className="flex h-9 items-center gap-2 rounded-xl border border-accent/20 bg-accent/10 px-3 text-xs font-bold text-accent transition-all hover:bg-accent/20"
                            >
                              <Activity className="h-3.5 w-3.5" />
                              {trailerTableText.actions.detail}
                            </button>
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                onEdit(trailer);
                              }}
                              className="flex h-9 w-9 items-center justify-center rounded-xl border border-border bg-elevated text-secondary transition-all hover:bg-surface hover:text-primary"
                              title={trailerTableText.actions.edit}
                            >
                              <Edit2 className="h-4 w-4" />
                            </button>
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                trailer.id && handleOptimisticDelete(trailer);
                              }}
                              disabled={
                                !!trailer.id && deletingIds.has(trailer.id)
                              }
                              className="flex h-9 w-9 items-center justify-center rounded-xl border border-danger/20 bg-danger/10 text-danger transition-all hover:bg-danger/20 disabled:opacity-50"
                              title={trailerTableText.actions.delete}
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </div>
                        </td>
                      </motion.tr>
                    ))}
                </AnimatePresence>
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          <AnimatePresence>
            {trailers
              .filter((trailer) => trailer.id && !deletedIds.has(trailer.id))
              .map((trailer, index) => (
                <motion.div
                  key={trailer.id}
                  initial={{ opacity: 0, scale: 0.95, y: 20 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.9, y: -20 }}
                  transition={{ duration: 0.3, delay: index * 0.05 }}
                  className={cn(
                    "group relative flex flex-col overflow-hidden rounded-[24px] border border-border bg-surface/80 p-6 shadow-lg transition-all hover:-translate-y-1 hover:border-accent/40 hover:shadow-accent/5",
                    trailer.id &&
                      deletingIds.has(trailer.id) &&
                      "pointer-events-none opacity-50 grayscale",
                  )}
                >
                  <div className="absolute right-0 top-0 h-32 w-32 -translate-y-1/2 translate-x-1/2 rounded-full bg-accent/5 blur-[40px] opacity-0 transition-opacity duration-500 group-hover:opacity-100" />

                  <div className="absolute right-6 top-6 z-10">
                    <span
                      className={cn(
                        "flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest shadow-sm",
                        trailer.aktif
                          ? "border-success/30 bg-success/10 text-success shadow-success/10"
                          : "border-border bg-elevated text-secondary",
                      )}
                    >
                      <span
                        className={cn(
                          "h-2 w-2 rounded-full",
                          trailer.aktif ? "bg-success" : "bg-secondary",
                        )}
                      />
                      {trailer.aktif
                        ? trailerTableText.status.active
                        : trailerTableText.status.inactive}
                    </span>
                  </div>

                  <div className="relative z-10 mb-6 flex items-start gap-4">
                    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-border bg-elevated shadow-inner">
                      <Container className="h-7 w-7 text-primary transition-colors group-hover:text-accent" />
                    </div>
                    <div className="min-w-0 flex-1 pr-20">
                      <div className="mb-2 inline-flex items-center rounded border border-border bg-elevated px-2.5 py-1 text-xs font-black tracking-widest text-accent shadow-md">
                        {trailer.plaka}
                      </div>
                      <h3 className="truncate text-lg font-black text-primary transition-colors group-hover:text-accent">
                        {trailer.marka || trailerTableText.labels.unknownBrand}
                      </h3>
                      <p className="text-[10px] font-bold uppercase tracking-wider text-secondary">
                        {trailer.tipi}
                      </p>
                    </div>
                  </div>

                  <div className="relative z-10 mb-6 grid grid-cols-2 gap-3">
                    <div className="flex flex-col gap-1 rounded-xl border border-border bg-elevated p-3">
                      <div className="mb-0.5 flex items-center gap-1.5 text-secondary">
                        <Calendar className="h-3.5 w-3.5" />
                        <span className="text-[10px] font-bold uppercase tracking-wider">
                          {trailerTableText.labels.modelYear}
                        </span>
                      </div>
                      <span className="text-sm font-bold text-primary">
                        {trailer.yil || "-"}
                      </span>
                    </div>
                    <div className="flex flex-col gap-1 rounded-xl border border-border bg-elevated p-3">
                      <div className="mb-0.5 flex items-center gap-1.5 text-secondary">
                        <Weight className="h-3.5 w-3.5" />
                        <span className="text-[10px] font-bold uppercase tracking-wider">
                          {trailerTableText.labels.emptyWeight}
                        </span>
                      </div>
                      <span className="text-sm font-bold text-primary">
                        {trailer.bos_agirlik_kg?.toLocaleString("tr-TR") || "-"}{" "}
                        kg
                      </span>
                    </div>
                    <div className="col-span-2 flex flex-col gap-1 rounded-xl border border-border bg-elevated p-3">
                      <div className="mb-0.5 flex items-center gap-1.5 text-secondary">
                        <Disc className="h-3.5 w-3.5" />
                        <span className="text-[10px] font-bold uppercase tracking-wider">
                          {trailerTableText.labels.tireCountCard}
                        </span>
                      </div>
                      <span className="text-sm font-bold text-primary">
                        {trailer.lastik_sayisi || "-"}{" "}
                        {trailerTableText.labels.pieceSuffix}
                      </span>
                    </div>
                  </div>

                  <div className="flex-1" />

                  <div className="relative z-10 flex items-center justify-between border-t border-border pt-4">
                    <button
                      onClick={() => onViewDetail(trailer)}
                      className="flex h-10 items-center gap-2 rounded-xl border border-accent/20 bg-accent/10 px-4 text-xs font-bold text-accent transition-all hover:border-accent/40 hover:bg-accent/20"
                    >
                      <Activity className="h-4 w-4" />
                      {trailerTableText.actions.details}
                    </button>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => onEdit(trailer)}
                        className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-elevated text-secondary transition-all hover:bg-surface hover:text-primary"
                        title={trailerTableText.actions.edit}
                      >
                        <Edit2 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() =>
                          trailer.id && handleOptimisticDelete(trailer)
                        }
                        disabled={!!trailer.id && deletingIds.has(trailer.id)}
                        className="flex h-10 w-10 items-center justify-center rounded-xl border border-danger/20 bg-danger/10 text-danger transition-all hover:bg-danger/20 disabled:opacity-50"
                        title={trailerTableText.actions.delete}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </motion.div>
              ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
