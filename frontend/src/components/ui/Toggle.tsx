import { cn } from "../../lib/utils";

export interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
  size?: "sm" | "md";
  className?: string;
}

export function Toggle({
  checked,
  onChange,
  label,
  disabled = false,
  size = "md",
  className,
}: ToggleProps) {
  const handleToggle = () => {
    if (!disabled) {
      onChange(!checked);
    }
  };

  const sizes = {
    sm: {
      track: "w-[32px] h-[16px]",
      thumb: "w-[12px] h-[12px]",
      translate: "translate-x-[16px]",
    },
    md: {
      track: "w-[44px] h-[24px]",
      thumb: "w-[20px] h-[20px]",
      translate: "translate-x-[20px]",
    },
  };

  return (
    <label
      className={cn(
        "inline-flex items-center gap-[8px] cursor-pointer select-none",
        disabled && "cursor-not-allowed opacity-50",
        className,
      )}
    >
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={handleToggle}
        className={cn(
          "relative inline-flex shrink-0 rounded-full transition-colors duration-200 ease-in-out border border-transparent",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/20 focus-visible:ring-offset-2",
          sizes[size].track,
          checked ? "bg-accent" : "bg-surface border border-border",
        )}
      >
        <span
          className={cn(
            "pointer-events-none inline-block rounded-full bg-base shadow-sm ring-0 transition-transform duration-200 ease-[cubic-bezier(0.16,1,0.3,1)]",
            sizes[size].thumb,
            "absolute top-1/2 -translate-y-1/2 left-[2px]",
            checked && sizes[size].translate,
          )}
        />
      </button>
      {label && (
        <span className="text-[14px] font-medium text-primary">{label}</span>
      )}
    </label>
  );
}
