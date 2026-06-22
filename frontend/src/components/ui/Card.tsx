import * as React from "react";
import { cn } from "../../lib/utils";

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  padding?: "none" | "sm" | "md" | "lg";
  hoverEffect?: boolean;
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  (
    { children, className, padding = "md", hoverEffect = false, ...props },
    ref,
  ) => {
    // LojiNext v2.0 Card Rules:
    // border: 1px solid var(--border)
    // box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)
    // Hover: shadow deepens, 150ms
    // padding: 20px (md)
    // border-radius: 10px

    const paddingStyles = {
      none: "p-0",
      sm: "p-[12px]",
      md: "p-[20px]",
      lg: "p-[32px]",
    };

    return (
      <div
        ref={ref}
        className={cn(
          "bg-surface border border-border rounded-[10px]",
          "shadow-[0_1px_3px_rgba(0,0,0,0.06),0_1px_2px_rgba(0,0,0,0.04)]",
          "transition-shadow duration-150",
          hoverEffect &&
            "hover:shadow-[0_4px_6px_-1px_rgba(0,0,0,0.1),0_2px_4px_-1px_rgba(0,0,0,0.06)] hover:-translate-y-[1px] transition-all",
          paddingStyles[padding],
          className,
        )}
        {...props}
      >
        {children}
      </div>
    );
  },
);

Card.displayName = "Card";
