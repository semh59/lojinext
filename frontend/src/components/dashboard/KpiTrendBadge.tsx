import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

interface Props {
  /** Percentage change vs. previous period. Positive = increase, negative = decrease. */
  trend: number | null | undefined;
  /** When true, downward movement is good (e.g. consumption). Defaults to upward = good. */
  invert?: boolean;
}

export function KpiTrendBadge({ trend, invert = false }: Props) {
  if (trend === null || trend === undefined || Number.isNaN(trend)) {
    return null;
  }

  const isZero = Math.abs(trend) < 0.05;
  const positive = trend > 0;
  const good = isZero ? null : invert ? !positive : positive;
  const Icon = isZero ? Minus : positive ? ArrowUpRight : ArrowDownRight;
  const colorClass = isZero
    ? "text-secondary bg-elevated/60"
    : good
      ? "text-success bg-success/10"
      : "text-danger bg-danger/10";

  const formatted = `${positive && !isZero ? "+" : ""}${trend.toFixed(1)}%`;

  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded-card px-1.5 py-0.5 text-[10px] font-semibold ${colorClass}`}
      title="Geçen aya göre değişim"
    >
      <Icon className="h-3 w-3" />
      {formatted}
    </span>
  );
}
