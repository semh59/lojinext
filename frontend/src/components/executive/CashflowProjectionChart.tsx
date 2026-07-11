import { AlertCircle, Loader2, Receipt } from "lucide-react";
import {
  Bar,
  BarChart,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { cn } from "@/lib/utils";
import { useCashflow } from "@/hooks/useExecutive";
import { useExecutiveResources } from "@/resources/useResources";
import { useLocale } from "../../hooks/useLocale";

interface Props {
  className?: string;
}

export function CashflowProjectionChart({ className }: Props) {
  const { executiveText } = useExecutiveResources();
  const locale = useLocale();
  const { data, isLoading, error } = useCashflow(90);
  const t = executiveText.cashflow;

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

  const chartData = data.weeks.map((w) => {
    const d = new Date(w.week_start);
    return {
      // Was hardcoded `${getDate()}.${getMonth()+1}` (Turkish day.month
      // convention) regardless of app language — used the locale-aware
      // formatter already in scope instead.
      week: d.toLocaleDateString(locale, { day: "numeric", month: "numeric" }),
      fuel: w.fuel_tl,
      maintenance: w.maintenance_tl,
      penalty: w.penalty_tl,
    };
  });

  return (
    <div
      className={cn(
        "rounded-modal border border-border bg-surface p-6 shadow-sm",
        className,
      )}
    >
      <div className="mb-4 flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Receipt className="h-4 w-4 text-secondary" />
          <h3 className="text-xs font-bold uppercase tracking-widest text-secondary">
            {t.title}
          </h3>
        </div>
        <div className="text-right">
          <p className="text-[10px] uppercase tracking-wider text-secondary">
            {t.grandTotal}
          </p>
          <p className="font-mono text-lg font-bold text-primary">
            ₺{data.grand_total_tl.toLocaleString(locale)}
          </p>
        </div>
      </div>

      <div className="h-48">
        {/* Inside a CSS grid column (md:col-span-8 on ExecutivePage), the
            grid track width isn't committed on ResponsiveContainer's first
            ResizeObserver callback — it measures -1x-1, renders an empty
            chart, remeasures, and repeats several times per mount (visible
            as repeated "width(-1) and height(-1)" console warnings). Explicit
            min dimensions give it a valid size immediately so it never
            renders the -1 frame or loops. */}
        <ResponsiveContainer
          width="100%"
          height="100%"
          minWidth={200}
          minHeight={120}
        >
          <BarChart data={chartData}>
            <XAxis
              dataKey="week"
              tick={{ fontSize: 10 }}
              stroke="currentColor"
              className="text-tertiary"
            />
            <YAxis
              tick={{ fontSize: 10 }}
              stroke="currentColor"
              className="text-tertiary"
              tickFormatter={(v: number) =>
                v >= 1000 ? `${(v / 1000).toFixed(0)}K` : `${v}`
              }
            />
            <Tooltip
              contentStyle={{
                fontSize: "12px",
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: 8,
              }}
              formatter={(value: unknown, name: unknown) => [
                `₺${Number(value ?? 0).toLocaleString(locale)}`,
                String(name ?? ""),
              ]}
            />
            <Legend wrapperStyle={{ fontSize: "11px", paddingTop: 8 }} />
            <Bar
              dataKey="fuel"
              stackId="cost"
              fill="#3b82f6"
              name={t.legendFuel}
            />
            <Bar
              dataKey="maintenance"
              stackId="cost"
              fill="#f59e0b"
              name={t.legendMaintenance}
            />
            <Bar
              dataKey="penalty"
              stackId="cost"
              fill="#dc2626"
              name={t.legendPenalty}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-border/40 pt-3 text-[10px] text-tertiary">
        <span>
          {t.dieselPrice}: ₺{data.assumptions.diesel_price_tl}
        </span>
        <span>
          {t.avgBakimCost}: ₺
          {data.assumptions.avg_bakim_cost_tl?.toLocaleString(locale) ?? "—"}
        </span>
        <span>
          {t.upcomingBakim}: {data.assumptions.upcoming_bakim_count ?? 0}
        </span>
      </div>
    </div>
  );
}
