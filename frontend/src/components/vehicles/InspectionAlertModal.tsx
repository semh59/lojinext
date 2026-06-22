import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Loader2, Truck, X } from "lucide-react";
import { vehicleService, type InspectionAlertItem } from "../../api/vehicles";

interface InspectionAlertModalProps {
  isOpen: boolean;
  onClose: () => void;
  withinDays?: number;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) return iso;
  return `${match[3]}.${match[2]}.${match[1]}`;
}

export function InspectionAlertModal({
  isOpen,
  onClose,
  withinDays = 30,
}: InspectionAlertModalProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["vehicles", "inspection-alerts", withinDays],
    queryFn: () => vehicleService.getInspectionAlerts(withinDays),
    staleTime: 5 * 60 * 1000,
    enabled: isOpen,
  });

  if (!isOpen) return null;

  const totalExpiring = data?.expiring.length ?? 0;
  const totalOverdue = data?.overdue.length ?? 0;
  const totalCount = totalExpiring + totalOverdue;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
      <div className="relative flex max-h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-modal border border-border bg-surface shadow-2xl">
        <div className="flex items-center justify-between border-b border-border bg-elevated/40 p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-warning" />
            <div>
              <h3 className="text-sm font-semibold text-primary">
                Muayene Uyarıları
              </h3>
              <p className="text-[11px] text-secondary">
                Önümüzdeki {withinDays} gün + geçmiş muayeneler
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-1.5 text-secondary transition-colors hover:bg-elevated hover:text-primary"
            aria-label="Kapat"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="custom-scrollbar flex-1 overflow-y-auto p-5">
          {isLoading ? (
            <div className="flex items-center justify-center gap-3 py-12 text-secondary">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span className="text-sm">Yükleniyor…</span>
            </div>
          ) : isError ? (
            <div className="rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
              Muayene listesi alınamadı.
            </div>
          ) : totalCount === 0 ? (
            <div className="flex items-center gap-3 rounded-card border border-success/20 bg-success/5 px-4 py-3">
              <CheckCircle2 className="h-5 w-5 text-success" />
              <p className="text-sm text-secondary">
                Yaklaşan veya geçmiş muayene yok. Filo bu konuda temiz.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              <Section
                title={`Geçmiş Muayene (${totalOverdue})`}
                items={data?.overdue ?? []}
                emptyText="Geçmiş muayene yok."
                tone="danger"
              />
              <Section
                title={`Yaklaşan Muayene (${totalExpiring})`}
                items={data?.expiring ?? []}
                emptyText="Yaklaşan muayene yok."
                tone="warning"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({
  title,
  items,
  emptyText,
  tone,
}: {
  title: string;
  items: InspectionAlertItem[];
  emptyText: string;
  tone: "danger" | "warning";
}) {
  const toneClass = tone === "danger" ? "text-danger" : "text-warning";
  const badgeBg =
    tone === "danger"
      ? "bg-danger/10 border-danger/20"
      : "bg-warning/10 border-warning/20";

  if (items.length === 0) {
    return (
      <div>
        <h4
          className={`mb-2 text-[11px] font-bold uppercase tracking-widest ${toneClass}`}
        >
          {title}
        </h4>
        <p className="text-xs text-secondary">{emptyText}</p>
      </div>
    );
  }

  return (
    <div>
      <h4
        className={`mb-2 text-[11px] font-bold uppercase tracking-widest ${toneClass}`}
      >
        {title}
      </h4>
      <ul className="space-y-2">
        {items.map((v) => (
          <li
            key={v.id}
            className="flex items-center justify-between gap-3 rounded-card border border-border bg-elevated/30 px-3 py-2"
          >
            <div className="min-w-0 flex items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-card bg-surface">
                <Truck className="h-4 w-4 text-secondary" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-primary">
                  <span className="font-mono">{v.plaka}</span>
                  {(v.marka || v.model) && (
                    <span className="ml-2 text-xs font-normal text-secondary">
                      {[v.marka, v.model, v.yil].filter(Boolean).join(" · ")}
                    </span>
                  )}
                </p>
                <p className="text-[11px] text-secondary">
                  Muayene:{" "}
                  <span className="font-mono">
                    {formatDate(v.muayene_tarihi)}
                  </span>
                </p>
              </div>
            </div>
            {v.days_remaining != null && (
              <span
                className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${badgeBg} ${toneClass}`}
              >
                {v.days_remaining < 0
                  ? `${Math.abs(v.days_remaining)} gün geçmiş`
                  : `${v.days_remaining} gün kaldı`}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
