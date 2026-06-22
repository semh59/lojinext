import { AnimatePresence, motion } from "framer-motion";
import { Award, BrainCircuit, Edit2, Phone, Star, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Driver } from "../../types";
import { cn } from "../../lib/utils";
import { useDriversResources } from "../../resources/useResources";

interface DriverTableProps {
  drivers: Driver[];
  onEdit: (driver: Driver) => void;
  onDelete: (driver: Driver) => void;
  onScoreClick: (driver: Driver) => void;
  onPerformanceClick: (driver: Driver) => void;
  selectedIds?: number[];
  onToggleSelection?: (id: number) => void;
  onToggleAll?: (allIds: number[], allSelected: boolean) => void;
}

export function DriverTable({
  drivers,
  onEdit,
  onDelete,
  onScoreClick,
  onPerformanceClick,
  selectedIds,
  onToggleSelection,
  onToggleAll,
}: DriverTableProps) {
  const { t } = useTranslation();
  const { driverTableText } = useDriversResources();
  const showSelection = !!onToggleSelection;
  const gridTemplate = showSelection
    ? "40px 1fr 140px 140px 140px 160px"
    : "1fr 140px 140px 140px 160px";

  const visibleIds = drivers
    .map((d) => d.id)
    .filter((id): id is number => id != null);
  const selectedSet = new Set(selectedIds ?? []);
  const allSelected =
    visibleIds.length > 0 && visibleIds.every((id) => selectedSet.has(id));

  return (
    <div className="overflow-hidden rounded-none border-none bg-surface">
      <div className="custom-scrollbar overflow-x-auto">
        <div className="min-w-[800px]">
          <div
            className="grid items-center border-b border-border bg-elevated/50 px-6 py-4"
            style={{ gridTemplateColumns: gridTemplate }}
          >
            {showSelection && (
              <input
                type="checkbox"
                checked={allSelected}
                onChange={() => onToggleAll?.(visibleIds, allSelected)}
                aria-label={t("common.select_all", "Select all")}
                className="h-4 w-4 cursor-pointer accent-accent"
              />
            )}
            <div className="text-[11px] font-bold uppercase tracking-widest text-secondary">
              {driverTableText.columns.driver}
            </div>
            <div className="text-[11px] font-bold uppercase tracking-widest text-secondary">
              {driverTableText.columns.contact}
            </div>
            <div className="text-[11px] font-bold uppercase tracking-widest text-secondary">
              {driverTableText.columns.score}
            </div>
            <div className="text-[11px] font-bold uppercase tracking-widest text-secondary">
              {driverTableText.columns.status}
            </div>
            <div className="text-right text-[11px] font-bold uppercase tracking-widest text-secondary">
              {driverTableText.columns.actions}
            </div>
          </div>

          <div className="divide-y divide-border">
            <AnimatePresence mode="popLayout">
              {drivers.map((driver, index) => (
                <motion.div
                  key={driver.id}
                  layout
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.98 }}
                  transition={{ duration: 0.2, delay: index * 0.02 }}
                  className="group grid items-center px-6 py-4 transition-all hover:bg-elevated/30"
                  style={{ gridTemplateColumns: gridTemplate }}
                >
                  {showSelection && (
                    <input
                      type="checkbox"
                      checked={driver.id != null && selectedSet.has(driver.id)}
                      onChange={() =>
                        driver.id != null && onToggleSelection?.(driver.id)
                      }
                      aria-label={t("common.select_item", "Select {{name}}", {
                        name: driver.ad_soyad,
                      })}
                      className="h-4 w-4 cursor-pointer accent-accent"
                      onClick={(e) => e.stopPropagation()}
                    />
                  )}
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-border bg-elevated font-bold text-accent shadow-sm">
                      {driver.ad_soyad[0]}
                    </div>
                    <div className="flex min-w-0 flex-col">
                      <span className="truncate text-sm font-bold text-primary">
                        {driver.ad_soyad}
                      </span>
                      <span className="truncate text-[10px] font-bold uppercase text-secondary">
                        {driverTableText.licenseSuffix(driver.ehliyet_sinifi)}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 text-xs font-medium tabular-nums text-primary">
                    <Phone className="h-3.5 w-3.5 text-secondary" />
                    {driver.telefon || "-"}
                  </div>

                  <div className="flex items-center gap-0.5">
                    {[...Array(5)].map((_, index) => (
                      <Star
                        key={index}
                        className={cn(
                          "h-3.5 w-3.5",
                          index < (driver.score || 0)
                            ? "fill-warning text-warning"
                            : "text-border",
                        )}
                      />
                    ))}
                  </div>

                  <div>
                    <div
                      className={cn(
                        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[10px] font-bold uppercase tracking-tight",
                        driver.aktif
                          ? "border-success/20 bg-success/10 text-success"
                          : "border-border bg-elevated text-secondary",
                      )}
                    >
                      <span
                        className={cn(
                          "h-1.5 w-1.5 rounded-full",
                          driver.aktif
                            ? "bg-success shadow-[0_0_8px_rgba(34,197,94,0.3)]"
                            : "bg-border",
                        )}
                      />
                      {driver.aktif
                        ? driverTableText.status.active
                        : driverTableText.status.inactive}
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-1">
                    <button
                      onClick={() => onPerformanceClick(driver)}
                      className="rounded-lg p-2 text-secondary transition-all hover:bg-info/10 hover:text-info focus:outline-none"
                      title={driverTableText.actions.aiAnalysis}
                    >
                      <BrainCircuit className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => onScoreClick(driver)}
                      className="rounded-lg p-2 text-secondary transition-all hover:bg-warning/10 hover:text-warning focus:outline-none"
                      title={driverTableText.actions.score}
                    >
                      <Award className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => onEdit(driver)}
                      className="rounded-lg p-2 text-secondary transition-all hover:bg-accent/10 hover:text-accent focus:outline-none"
                      title={driverTableText.actions.edit}
                    >
                      <Edit2 className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => onDelete(driver)}
                      className="rounded-lg p-2 text-secondary transition-all hover:bg-danger/10 hover:text-danger focus:outline-none"
                      title={driverTableText.actions.delete}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}
