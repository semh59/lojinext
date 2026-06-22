import * as React from "react";
import { Loader2 } from "lucide-react";
import { cn } from "../../lib/utils";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost" | "outline";
  size?: "sm" | "md" | "lg" | "icon";
  isLoading?: boolean;
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "primary",
      size = "md",
      isLoading,
      children,
      disabled,
      ...props
    },
    ref,
  ) => {
    const Comp = "button";

    // LojiNext v2.0 Button Rules:
    // Height 36px, font 14px, weight 500, radius 6px.
    // Hover and scale(0.97) interactions (150ms / 80ms).
    const baseStyles =
      "inline-flex items-center justify-center gap-2 font-medium text-[14px] rounded-[6px] transition-all duration-150 active:scale-[0.97] active:duration-75 disabled:opacity-60 disabled:pointer-events-none outline-none focus-visible:ring-2 focus-visible:ring-offset-2";

    const variants = {
      primary:
        "bg-accent text-bg-base hover:bg-accent/90 border border-transparent shadow-sm focus-visible:ring-accent/20",
      secondary:
        "bg-transparent border border-border text-primary hover:bg-elevated hover:border-secondary focus-visible:ring-secondary/20 shadow-sm",
      ghost:
        "bg-transparent text-secondary hover:text-primary hover:bg-elevated focus-visible:ring-secondary/20",
      danger:
        "bg-danger text-bg-base hover:bg-danger/90 border border-transparent shadow-sm focus-visible:ring-danger/20",
      outline:
        "bg-transparent border border-border text-primary hover:bg-elevated hover:text-accent focus-visible:ring-accent/20 shadow-sm",
    };

    const sizes = {
      sm: "h-[32px] px-[12px] text-[13px]",
      md: "h-[36px] px-[16px]", // 36px height as per rule
      lg: "h-[48px] px-[24px] text-[16px]",
      icon: "h-[36px] w-[36px] p-0 flex items-center justify-center",
    };

    return (
      <Comp
        className={cn(
          baseStyles,
          variants[variant],
          sizes[size],
          isLoading && "opacity-70 cursor-not-allowed",
          className,
        )}
        ref={ref}
        disabled={isLoading || disabled}
        {...props}
      >
        {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        {children}
      </Comp>
    );
  },
);
Button.displayName = "Button";

export { Button };
