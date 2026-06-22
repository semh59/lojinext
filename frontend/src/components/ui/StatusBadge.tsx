import { clsx } from "clsx";
import type { StatusMeta, StatusVariant } from "../../lib/status-labels";

const variantClasses: Record<StatusVariant, string> = {
  info: "border-info/30 bg-info/10 text-info",
  success: "border-success/30 bg-success/10 text-success",
  danger: "border-danger/30 bg-danger/10 text-danger",
  warning: "border-warning/30 bg-warning/10 text-warning",
  neutral: "border-border bg-elevated text-secondary",
};

interface StatusBadgeProps {
  meta: StatusMeta;
  size?: "xs" | "sm";
  className?: string;
}

export function StatusBadge({
  meta,
  size = "xs",
  className,
}: StatusBadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-xl border font-black uppercase tracking-widest",
        size === "xs" ? "px-2 py-1 text-[10px]" : "px-2.5 py-1.5 text-xs",
        variantClasses[meta.variant],
        className,
      )}
    >
      {meta.label}
    </span>
  );
}
