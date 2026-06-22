import { AlertCircle, Loader2, ShieldAlert, User2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { executiveText } from "@/resources/tr/executive";
import { useBusFactor } from "@/hooks/useExecutive";
import type { BusFactorRisk } from "@/api/executive";

interface Props {
  className?: string;
}

const RISK_STYLE: Record<BusFactorRisk, string> = {
  high: "bg-danger/10 text-danger border-danger/30",
  medium: "bg-warning/10 text-warning border-warning/30",
  low: "bg-success/10 text-success border-success/30",
};

const RISK_LABEL: Record<BusFactorRisk, string> = {
  high: executiveText.busFactor.riskHigh,
  medium: executiveText.busFactor.riskMedium,
  low: executiveText.busFactor.riskLow,
};

export function BusFactorWidget({ className }: Props) {
  const { data, isLoading, error } = useBusFactor(3);
  const t = executiveText.busFactor;

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
          <ShieldAlert className="h-4 w-4 text-secondary" />
          <div>
            <h3 className="text-xs font-bold uppercase tracking-widest text-secondary">
              {t.title}
            </h3>
            <p className="mt-0.5 text-[10px] text-tertiary">{t.subtitle}</p>
          </div>
        </div>
        <span
          className={cn(
            "inline-block rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider",
            RISK_STYLE[data.risk_level],
          )}
        >
          {RISK_LABEL[data.risk_level]}
        </span>
      </div>

      <div className="mb-3">
        <p className="text-[10px] uppercase tracking-wider text-secondary">
          {t.yearlyLoss}
        </p>
        <p className="mt-1 font-mono text-2xl font-bold text-primary">
          ₺{data.top_n_drivers_loss_tl.toLocaleString("tr-TR")}
        </p>
      </div>

      <div className="space-y-1.5">
        <p className="text-[10px] uppercase tracking-wider text-secondary">
          {t.topDriversAnonymized}
        </p>
        {data.top_n_drivers.map((d, i) => (
          <div
            key={i}
            className="flex items-center justify-between rounded-card border border-border/40 bg-elevated/30 px-2.5 py-1.5 text-[11px]"
          >
            <span className="flex items-center gap-1.5 text-secondary">
              <User2 className="h-3 w-3" />#{i + 1}
            </span>
            <span className="flex items-center gap-3 font-mono">
              <span>
                <span className="text-tertiary">{t.score}:</span>{" "}
                <span className="font-semibold text-primary">
                  {d.score.toFixed(2)}
                </span>
              </span>
              <span>
                <span className="text-tertiary">{t.yearlyKm}:</span>{" "}
                <span className="font-semibold text-primary">
                  {d.yearly_km.toLocaleString("tr-TR")}
                </span>
              </span>
            </span>
          </div>
        ))}
      </div>

      <p className="mt-3 text-[10px] italic text-tertiary">{t.piiNote}</p>
    </div>
  );
}
