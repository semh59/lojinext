import {
  AlertCircle,
  Loader2,
  TrendingUp,
  Wrench,
  Sparkles,
  ShieldX,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { useCrossFeature } from "@/hooks/useExecutive";
import { useExecutiveResources } from "@/resources/useResources";

interface Props {
  className?: string;
}

function ImpactRow({
  Icon,
  label,
  valueTl,
  tone,
}: {
  Icon: typeof Wrench;
  label: string;
  valueTl: number;
  tone: "danger" | "success" | "warning";
}) {
  const toneClass =
    tone === "danger"
      ? "text-danger"
      : tone === "success"
        ? "text-success"
        : "text-warning";
  const sign = tone === "success" ? "+" : "-";
  return (
    <div className="flex items-center justify-between rounded-card border border-border/40 bg-elevated/30 px-3 py-2">
      <span className="flex items-center gap-2 text-xs text-secondary">
        <Icon className={cn("h-3.5 w-3.5", toneClass)} />
        {label}
      </span>
      <span
        className={cn(
          "font-mono text-sm font-semibold tabular-nums",
          toneClass,
        )}
      >
        {sign} ₺{valueTl.toLocaleString("tr-TR")}
      </span>
    </div>
  );
}

export function CrossFeatureSavings({ className }: Props) {
  const { executiveText } = useExecutiveResources();
  const { data, isLoading, error } = useCrossFeature(90);
  const t = executiveText.crossFeature;

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

  const netImpact =
    data.coaching_savings_tl -
    data.maintenance_delay_loss_tl -
    data.theft_loss_tl;

  return (
    <div
      className={cn(
        "rounded-modal border border-border bg-surface p-6 shadow-sm",
        className,
      )}
    >
      <div className="mb-4">
        <h3 className="text-xs font-bold uppercase tracking-widest text-secondary">
          {t.title}
        </h3>
        <p className="mt-0.5 text-[10px] text-tertiary">{t.subtitle}</p>
      </div>

      <div className="space-y-2">
        <ImpactRow
          Icon={Wrench}
          label={t.maintenanceLoss}
          valueTl={data.maintenance_delay_loss_tl}
          tone="danger"
        />
        <ImpactRow
          Icon={Sparkles}
          label={t.coachingSavings}
          valueTl={data.coaching_savings_tl}
          tone="success"
        />
        <ImpactRow
          Icon={ShieldX}
          label={t.theftLoss}
          valueTl={data.theft_loss_tl}
          tone="danger"
        />
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-border/40 pt-3">
        <span className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-secondary">
          <TrendingUp className="h-3 w-3" />
          {t.netImpact}
        </span>
        <span
          className={cn(
            "font-mono text-lg font-bold tabular-nums",
            netImpact >= 0 ? "text-success" : "text-danger",
          )}
        >
          {netImpact >= 0 ? "+" : ""}₺
          {Math.abs(netImpact).toLocaleString("tr-TR")}
        </span>
      </div>

      <p className="mt-2 text-[10px] italic text-tertiary">
        {t.confidence}: {(data.confidence * 100).toFixed(0)}%
      </p>
    </div>
  );
}
