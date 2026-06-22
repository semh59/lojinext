import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { AnimatePresence, motion } from "framer-motion";
import { Edit2, Fuel, Trash2 } from "lucide-react";

import { FuelRecord } from "../../types";
import { useFuelResources } from "../../resources/useResources";

interface FuelTableProps {
  records: FuelRecord[];
  loading: boolean;
  onEdit: (record: FuelRecord) => void;
  onDelete: (record: FuelRecord) => void;
}

export function FuelTable({
  records,
  loading,
  onEdit,
  onDelete,
}: FuelTableProps) {
  const { fuelTableText } = useFuelResources();
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: records.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 80,
    overscan: 10,
  });

  if (loading) {
    return (
      <div className="space-y-4 p-8">
        {[...Array(5)].map((_, index) => (
          <div
            key={index}
            className="h-16 w-full animate-pulse rounded-xl border border-border bg-surface"
          />
        ))}
      </div>
    );
  }

  if (!records.length) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-border bg-surface p-20 text-center">
        <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-elevated">
          <span className="material-symbols-outlined text-4xl text-secondary font-variation-fill">
            local_gas_station
          </span>
        </div>
        <h3 className="text-xl font-black tracking-tight text-primary">
          {fuelTableText.emptyTitle}
        </h3>
        <p className="mt-1 font-medium text-secondary">
          {fuelTableText.emptyDescription}
        </p>
      </div>
    );
  }

  const gridTemplate =
    "minmax(120px, 1fr) minmax(130px, 1fr) minmax(200px, 1.5fr) minmax(130px, 1fr) minmax(130px, 1fr) minmax(140px, 1fr) 100px";

  return (
    <div
      ref={parentRef}
      className="custom-scrollbar max-h-[700px] w-full overflow-auto rounded-2xl border border-border bg-surface"
    >
      <div className="min-w-[1050px]">
        <div
          className="sticky top-0 z-20 grid items-center border-b border-border bg-elevated/90 px-6 py-4 backdrop-blur-md"
          style={{ gridTemplateColumns: gridTemplate }}
        >
          <div className="text-[10px] font-bold uppercase tracking-widest text-secondary">
            {fuelTableText.headers.dateTime}
          </div>
          <div className="text-[10px] font-bold uppercase tracking-widest text-secondary">
            {fuelTableText.headers.plate}
          </div>
          <div className="text-[10px] font-bold uppercase tracking-widest text-secondary">
            {fuelTableText.headers.stationReceipt}
          </div>
          <div className="text-right text-[10px] font-bold uppercase tracking-widest text-secondary">
            {fuelTableText.headers.liters}
          </div>
          <div className="text-right text-[10px] font-bold uppercase tracking-widest text-secondary">
            {fuelTableText.headers.unitPrice}
          </div>
          <div className="text-right text-[10px] font-bold uppercase tracking-widest text-secondary">
            {fuelTableText.headers.totalAmount}
          </div>
          <div className="text-center text-[10px] font-bold uppercase tracking-widest text-secondary">
            {fuelTableText.headers.actions}
          </div>
        </div>

        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: "100%",
            position: "relative",
          }}
        >
          <AnimatePresence mode="popLayout">
            {virtualizer.getVirtualItems().map((virtualRow) => {
              const record = records[virtualRow.index];
              if (!record) return null;

              return (
                <motion.div
                  key={record.id}
                  layout
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                  className="group absolute left-0 grid w-full items-center border-b border-border px-6 py-3 transition-all hover:bg-elevated hover:shadow-sm"
                  style={{
                    height: `${virtualRow.size}px`,
                    top: `${virtualRow.start}px`,
                    gridTemplateColumns: gridTemplate,
                  }}
                >
                  <div className="flex flex-col">
                    <span className="text-sm font-bold text-primary">
                      {new Date(record.tarih).toLocaleDateString("tr-TR", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </span>
                    <span className="text-[10px] font-bold uppercase text-secondary">
                      {(record as { saat?: string }).saat ||
                        fuelTableText.defaults.time}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <div className="size-2 rounded-full bg-success shadow-sm shadow-success/20" />
                    <span className="text-sm font-black uppercase tracking-tight text-primary">
                      {record.plaka}
                    </span>
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-elevated">
                      <Fuel className="h-4 w-4 text-secondary" />
                    </div>
                    <div className="flex min-w-0 flex-col pr-4">
                      <span className="truncate text-sm font-bold text-primary">
                        {record.istasyon || fuelTableText.defaults.station}
                      </span>
                      <span className="truncate text-[10px] font-bold text-secondary">
                        {fuelTableText.receiptLabel}:{" "}
                        {record.fis_no || fuelTableText.defaults.receipt}
                      </span>
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="font-mono text-sm tabular-nums text-primary">
                      {record.litre.toLocaleString("en-US", {
                        minimumFractionDigits: 1,
                        maximumFractionDigits: 1,
                      })}{" "}
                      L
                    </span>
                  </div>

                  <div className="text-right">
                    <span className="whitespace-nowrap rounded bg-success/10 px-2 py-1 text-xs font-bold tabular-nums text-success">
                      {(record.fiyat_tl || 0).toLocaleString("tr-TR", {
                        style: "currency",
                        currency: "TRY",
                      })}{" "}
                      /L
                    </span>
                  </div>

                  <div className="text-right">
                    <span className="text-sm font-bold tabular-nums text-primary">
                      {record.toplam_tutar.toLocaleString("tr-TR", {
                        style: "currency",
                        currency: "TRY",
                      })}
                    </span>
                  </div>

                  <div className="flex items-center justify-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                      onClick={() => onEdit(record)}
                      className="rounded-lg p-2 text-secondary transition-all hover:bg-accent/10 hover:text-accent"
                      aria-label={fuelTableText.actions.edit}
                    >
                      <Edit2 className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => onDelete(record)}
                      className="rounded-lg p-2 text-secondary transition-all hover:bg-danger/10 hover:text-danger"
                      aria-label={fuelTableText.actions.delete}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
