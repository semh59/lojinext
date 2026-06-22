import * as React from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { cn } from "../../lib/utils";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  children: React.ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}

export function Modal({
  isOpen,
  onClose,
  title,
  children,
  size = "md",
  className,
}: ModalProps) {
  const [isMounted, setIsMounted] = React.useState(false);
  const titleId = React.useId();

  React.useEffect(() => {
    setIsMounted(true);
  }, []);

  React.useEffect(() => {
    if (!isOpen) return;

    document.body.style.overflow = "hidden";

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("keydown", handleEscape);
      document.body.style.overflow = "unset";
    };
  }, [isOpen, onClose]);

  if (!isMounted || !isOpen) return null;

  const sizeClasses = {
    sm: "max-w-md",
    md: "max-w-xl",
    lg: "max-w-3xl",
    xl: "max-w-5xl",
  };

  return createPortal(
    <div
      // LojiNext v2.0 Modal Overlay Rules: backdrop blur + fade
      className="fixed inset-0 z-[999] flex items-center justify-center p-[16px] bg-base/40 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        // LojiNext v2.0 Modal Rules: 14px radius, scale(0.96) -> scale(1) + fade 200ms entrance
        className={cn(
          "relative w-full rounded-[14px] bg-surface p-[32px] border border-border",
          "shadow-[0_20px_40px_-15px_rgba(0,0,0,0.1)]",
          // Framer Motion or Tailwind Animate rule equivalence
          "animate-in fade-in zoom-in-[0.96] duration-200",
          "max-h-[90vh] overflow-y-auto custom-scrollbar",
          sizeClasses[size],
          className,
        )}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
      >
        <button
          onClick={onClose}
          className="absolute right-[24px] top-[24px] rounded-full p-[8px] text-secondary hover:bg-elevated hover:text-primary transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-text-secondary"
        >
          <X className="h-[20px] w-[20px]" />
          <span className="sr-only">Kapat</span>
        </button>

        {title && (
          <div className="mb-[24px] pr-[40px]">
            <h2
              id={titleId}
              className="text-[20px] font-bold text-primary tracking-tight"
            >
              {title}
            </h2>
          </div>
        )}

        <div className="text-primary">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
