import { motion } from "framer-motion";
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from "lucide-react";
import { cn } from "../../lib/utils";

export type ToastType = "success" | "error" | "info" | "warning";

export interface ToastProps {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  onClose: (id: string) => void;
}

export function Toast({ id, type, title, message, onClose }: ToastProps) {
  // LojiNext v2.0 Toast Rules: Slide-in from top-right, auto-dismiss with shrink
  const variants = {
    initial: { opacity: 0, x: 50, scale: 0.95 },
    animate: {
      opacity: 1,
      x: 0,
      scale: 1,
      transition: { type: "spring", stiffness: 400, damping: 25 } as const,
    },
    exit: {
      opacity: 0,
      scale: 0.85,
      transition: { duration: 0.2, ease: "easeIn" } as const,
    },
  } as const;

  return (
    <motion.div
      layout
      variants={variants}
      initial="initial"
      animate="animate"
      exit="exit"
      className={cn(
        "pointer-events-auto w-full max-w-sm bg-surface p-[16px] rounded-[14px] border border-border shadow-lg flex gap-[16px] items-start relative overflow-hidden group mb-[12px]",
      )}
    >
      <div
        className={cn(
          "p-[8px] rounded-[10px] flex-shrink-0",
          type === "success" && "bg-success/10 text-success",
          type === "error" && "bg-danger/10 text-danger",
          type === "warning" && "bg-warning/10 text-warning",
          type === "info" && "bg-info/10 text-info",
        )}
      >
        {type === "success" && (
          <CheckCircle className="w-[20px] h-[20px]" strokeWidth={2.5} />
        )}
        {type === "error" && (
          <AlertCircle className="w-[20px] h-[20px]" strokeWidth={2.5} />
        )}
        {type === "warning" && (
          <AlertTriangle className="w-[20px] h-[20px]" strokeWidth={2.5} />
        )}
        {type === "info" && (
          <Info className="w-[20px] h-[20px]" strokeWidth={2.5} />
        )}
      </div>

      <div className="flex-1 pr-[24px]">
        <h4 className="text-[14px] font-bold text-primary leading-tight mb-[4px]">
          {title}
        </h4>
        {message && (
          <p className="text-[13px] text-secondary font-medium leading-relaxed">
            {message}
          </p>
        )}
      </div>

      <button
        onClick={() => onClose(id)}
        className="absolute top-[12px] right-[12px] p-[4px] rounded-[6px] hover:bg-elevated text-secondary transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-text-secondary"
      >
        <X className="w-[16px] h-[16px]" strokeWidth={2} />
      </button>

      {/* Progress Bar */}
      <motion.div
        initial={{ width: "100%" }}
        animate={{ width: "0%" }}
        transition={{ duration: 5, ease: "linear" }}
        className={cn(
          "absolute bottom-0 left-0 h-[3px]",
          type === "success" && "bg-success",
          type === "error" && "bg-danger",
          type === "warning" && "bg-warning",
          type === "info" && "bg-info",
        )}
      />
    </motion.div>
  );
}
