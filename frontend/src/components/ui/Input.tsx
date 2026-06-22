import * as React from "react";
import { cn } from "../../lib/utils";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
  helperText?: string;
  label?: string;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, error, helperText, label, id, ...props }, ref) => {
    const generatedId = React.useId();
    const inputId = id || (label ? generatedId : undefined);

    return (
      <div className="w-full flex flex-col gap-[6px]">
        {label && (
          <label
            htmlFor={inputId}
            className="text-[13px] font-medium text-primary"
          >
            {label}
          </label>
        )}
        <div className="relative">
          <input
            id={inputId}
            type={type}
            className={cn(
              // LojiNext v2.0 Input Rules: 40px height, 14px, border + bg-surface, radius 6px
              // Focus border glow (accent color, 200ms)
              "flex h-[40px] w-full rounded-[6px] border border-border bg-surface px-[16px] py-[8px] text-[14px] text-primary",
              "placeholder:text-secondary transition-all duration-200 outline-none",
              "focus:border-accent focus:ring-2 focus:ring-accent/5",
              "disabled:cursor-not-allowed disabled:bg-elevated disabled:text-secondary disabled:border-border",
              error &&
                "border-danger focus:border-danger focus:ring-danger/5 animate-shake",
              className,
            )}
            ref={ref}
            aria-invalid={error ? "true" : "false"}
            {...props}
          />
        </div>
        {helperText && (
          <p
            className={cn(
              "text-[12px] mt-1",
              error ? "text-danger" : "text-secondary",
            )}
          >
            {helperText}
          </p>
        )}
      </div>
    );
  },
);
Input.displayName = "Input";

export { Input };
