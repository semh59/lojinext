import { AlertCircle, Calendar, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { executiveText } from "@/resources/tr/executive";
import { useCompliance } from "@/hooks/useExecutive";
import type { ComplianceRisk } from "@/api/executive";

interface Props {
  className?: string;
}

const RISK_STYLE: Record<ComplianceRisk, string> = {
  overdue: "bg-danger/10 text-danger border-danger/30",
  soon: "bg-warning/10 text-warning border-warning/30",
  normal: "bg-info/10 text-info border-info/30",
  low: "bg-success/10 text-success border-success/30",
};

const RISK_LABEL: Record<ComplianceRisk, string> = {
  overdue: executiveText.compliance.overdue,
  soon: executiveText.compliance.soon,
  normal: executiveText.compliance.normal,
  low: executiveText.compliance.low,
};

function formatDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${m[3]}.${m[2]}.${m[1]}`;
}

export function ComplianceHeatmap({ className }: Props) {
  const { data, isLoading, error } = useCompliance(90);
  const t = executiveText.compliance;

  if (isLoading) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 rounded-modal border border-border bg-surface p-6 shadow-sm",
          className,
        )}
      >
        <Loader2 className="h-4 w-4 animate-spin text-secondary" />
        <span className="text-sm text-secondary">{t.title}…</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div
        className={cn(
          "flex items-start gap-2 rounded-modal border border-danger/30 bg-danger/5 p-4 text-sm text-danger",
          className,
        )}
      >
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
        {executiveText.errors.loadFailed}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-modal border border-border bg-surface p-6 shadow-sm",
        className,
      )}
    >
      <div className="mb-4 flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-secondary" />
          <div>
            <h3 className="text-xs font-bold uppercase tracking-widest text-secondary">
              {t.title}
            </h3>
            <p className="mt-0.5 text-[10px] text-tertiary">{t.subtitle}</p>
          </div>
        </div>
        <div className="flex gap-2 text-[10px]">
          {data.overdue_count > 0 && (
            <span className="rounded-full border border-danger/30 bg-danger/10 px-2 py-0.5 font-bold text-danger">
              {data.overdue_count} {t.overdue}
            </span>
          )}
          {data.soon_count > 0 && (
            <span className="rounded-full border border-warning/30 bg-warning/10 px-2 py-0.5 font-bold text-warning">
              {data.soon_count} {t.soon}
            </span>
          )}
        </div>
      </div>

      {data.items.length === 0 ? (
        <p className="rounded-card border border-success/20 bg-success/5 px-3 py-3 text-xs text-secondary">
          {t.empty}
        </p>
      ) : (
        <div className="custom-scrollbar max-h-72 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-elevated/40">
              <tr>
                <th className="px-2 py-1.5 text-left font-bold uppercase tracking-wider text-secondary text-[10px]">
                  {t.columns.entity}
                </th>
                <th className="px-2 py-1.5 text-left font-bold uppercase tracking-wider text-secondary text-[10px]">
                  {t.columns.plaka}
                </th>
                <th className="px-2 py-1.5 text-right font-bold uppercase tracking-wider text-secondary text-[10px]">
                  {t.columns.expiry}
                </th>
                <th className="px-2 py-1.5 text-right font-bold uppercase tracking-wider text-secondary text-[10px]">
                  {t.columns.daysUntil}
                </th>
                <th className="px-2 py-1.5 text-center font-bold uppercase tracking-wider text-secondary text-[10px]">
                  {t.columns.risk}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {data.items.map((item) => (
                <tr
                  key={`${item.entity_type}-${item.entity_id}`}
                  className="hover:bg-elevated/20"
                >
                  <td className="px-2 py-1.5 text-secondary">
                    {t.entityType[item.entity_type]}
                  </td>
                  <td className="px-2 py-1.5 font-mono text-primary">
                    {item.plaka}
                  </td>
                  <td className="px-2 py-1.5 text-right font-mono text-tertiary">
                    {formatDate(item.expiry_date)}
                  </td>
                  <td
                    className={cn(
                      "px-2 py-1.5 text-right font-mono tabular-nums",
                      item.days_until < 0
                        ? "text-danger font-semibold"
                        : "text-primary",
                    )}
                  >
                    {item.days_until > 0 ? "+" : ""}
                    {item.days_until}
                  </td>
                  <td className="px-2 py-1.5 text-center">
                    <span
                      className={cn(
                        "inline-block rounded-full border px-1.5 py-0.5 text-[10px] font-bold uppercase",
                        RISK_STYLE[item.risk_level],
                      )}
                    >
                      {RISK_LABEL[item.risk_level]}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="mt-3 text-[10px] italic text-tertiary">{t.notes.v2}</p>
    </div>
  );
}
