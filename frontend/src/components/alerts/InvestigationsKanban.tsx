import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import {
  investigationService,
  type Investigation,
  type InvestigationStatus,
} from "../../api/investigations";
import { InvestigationCard } from "./InvestigationCard";
import { InvestigationDetailDialog } from "./InvestigationDetailDialog";
import { useInvestigationsResources } from "../../resources/useResources";

const COLUMN_ORDER: InvestigationStatus[] = [
  "open",
  "assigned",
  "investigating",
  "resolved",
  "closed",
];

export function InvestigationsKanban() {
  const { investigationsText } = useInvestigationsResources();
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["investigations", "list", 30],
    queryFn: () => investigationService.list({ days: 30, limit: 200 }),
    staleTime: 60 * 1000,
    refetchOnWindowFocus: true,
  });

  const byStatus = useMemo(() => {
    const out: Record<InvestigationStatus, Investigation[]> = {
      open: [],
      assigned: [],
      investigating: [],
      resolved: [],
      closed: [],
    };
    for (const inv of data ?? []) {
      const s = (inv.status ?? "open") as InvestigationStatus;
      if (out[s]) out[s].push(inv);
    }
    return out;
  }, [data]);

  const totalCount = data?.length ?? 0;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold text-primary">
          {investigationsText.sectionTitle}
        </h2>
        <span className="text-xs text-secondary">({totalCount} aktif)</span>
        {isLoading && (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-secondary" />
        )}
      </div>

      {!isLoading && totalCount === 0 ? (
        <p className="rounded-card border border-border bg-elevated/30 px-4 py-3 text-sm text-secondary">
          {investigationsText.emptyKanban}
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {COLUMN_ORDER.map((status) => {
            const items = byStatus[status];
            return (
              <div
                key={status}
                className="flex flex-col gap-2 rounded-modal border border-border bg-elevated/20 p-3 min-h-[180px]"
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-[10px] font-bold uppercase tracking-widest text-secondary">
                    {investigationsText.columnLabels[status]}
                  </h3>
                  <span className="text-[10px] font-bold text-tertiary tabular-nums">
                    {items.length}
                  </span>
                </div>
                {items.length === 0 ? (
                  <p className="text-[10px] text-tertiary italic">—</p>
                ) : (
                  items.map((inv) => (
                    <InvestigationCard
                      key={inv.id}
                      investigation={inv}
                      onClick={() => setSelectedId(inv.id)}
                    />
                  ))
                )}
              </div>
            );
          })}
        </div>
      )}

      <InvestigationDetailDialog
        investigationId={selectedId}
        onClose={() => setSelectedId(null)}
      />
    </div>
  );
}
