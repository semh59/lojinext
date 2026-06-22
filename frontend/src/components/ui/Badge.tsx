import * as React from "react";
import { cn } from "../../lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "success" | "warning" | "danger" | "info";
  pulse?: boolean;
}

function Badge({
  className,
  variant = "default",
  pulse = false,
  children,
  ...props
}: BadgeProps) {
  // LojiNext v2.0 Badge Rules:
  // Rounded-full (999px), colored bg at 12% opacity, colored text
  // e.g. "Aktif" → success color bg+text, dot pulse

  const variants = {
    default: "bg-secondary/10 text-secondary",
    success: "bg-success/10 text-success",
    warning: "bg-warning/10 text-warning",
    danger: "bg-danger/10 text-danger",
    info: "bg-info/10 text-info",
  };

  const dotColors = {
    default: "bg-secondary",
    success: "bg-success",
    warning: "bg-warning",
    danger: "bg-danger",
    info: "bg-info",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center gap-[6px] rounded-full px-[10px] py-[4px] text-[12px] font-semibold tracking-wide transition-colors",
        variants[variant],
        className,
      )}
      {...props}
    >
      {pulse && (
        <span className="relative flex h-[6px] w-[6px]">
          <span
            className={cn(
              "animate-ping absolute inline-flex h-full w-full rounded-full opacity-75",
              dotColors[variant],
            )}
          ></span>
          <span
            className={cn(
              "relative inline-flex rounded-full h-[6px] w-[6px]",
              dotColors[variant],
            )}
          ></span>
        </span>
      )}
      {children}
    </div>
  );
}

export { Badge };
