import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface LojiNextLogoProps {
  className?: string;
  iconSize?: number;
  textSize?: string;
  showText?: boolean;
  theme?: "light" | "dark";
}

/**
 * LojiNext Logo Component
 * Incorporates stylized truck and logistics details in a minimalist geometric form.
 */
export const LojiNextLogo = ({
  className,
  iconSize = 36,
  textSize = "text-xl",
  showText = true,
  theme = "light",
}: LojiNextLogoProps) => {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="relative flex items-center justify-center"
        style={{ width: iconSize, height: iconSize }}
      >
        {/* Truck / Logistics Icon */}
        <svg
          width={iconSize}
          height={iconSize}
          viewBox="0 0 40 40"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="drop-shadow-sm"
        >
          {/* Shadow / Glow Base */}
          <circle
            cx="20"
            cy="20"
            r="18"
            fill="url(#paint0_linear)"
            fillOpacity="0.1"
          />

          {/* Stylized Truck Head */}
          <path
            d="M10 14C10 12.3431 11.3431 11 13 11H27C28.6569 11 30 12.3431 30 14V26C30 27.6569 28.6569 29 27 29H13C11.3431 29 10 27.6569 10 26V14Z"
            className={theme === "light" ? "fill-accent" : "fill-bg-base"}
          />

          {/* Windshield Detail */}
          <path
            d="M13 15C13 14.4477 13.4477 14 14 14H26C26.5523 14 27 14.4477 27 15V19C27 19.5523 26.5523 20 26 20H14C13.4477 20 13 19.5523 13 19V15Z"
            className={theme === "light" ? "fill-bg-base" : "fill-accent"}
            fillOpacity="0.9"
          />

          {/* Grill / Logistics Details (Simplified LN pattern) */}
          <rect
            x="15"
            y="23"
            width="10"
            height="1.5"
            rx="0.75"
            className={theme === "light" ? "fill-bg-base" : "fill-primary"}
            fillOpacity="0.6"
          />
          <rect
            x="15"
            y="25.5"
            width="10"
            height="1.5"
            rx="0.75"
            className={theme === "light" ? "fill-bg-base" : "fill-primary"}
            fillOpacity="0.4"
          />
          <rect
            x="18"
            y="21.5"
            width="4"
            height="1"
            rx="0.5"
            className={theme === "light" ? "fill-bg-base" : "fill-primary"}
            fillOpacity="0.8"
          />

          {/* Headlights */}
          <circle cx="13" cy="24.5" r="1.5" className="fill-info" />
          <circle cx="27" cy="24.5" r="1.5" className="fill-info" />

          {/* Route Line (Subtle bottom flow) */}
          <path
            d="M8 34H32"
            className="stroke-accent"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeOpacity="0.15"
          />
          <path
            d="M16 34H28"
            className="stroke-accent"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeDasharray="2 4"
          />

          <defs>
            <linearGradient
              id="paint0_linear"
              x1="20"
              y1="2"
              x2="20"
              y2="38"
              gradientUnits="userSpaceOnUse"
            >
              <stop offset="0" stopColor="var(--accent)" />
              <stop offset="1" stopColor="var(--accent)" stopOpacity="0.8" />
            </linearGradient>
          </defs>
        </svg>
      </motion.div>

      {showText && (
        <span
          className={cn(
            "font-extrabold tracking-tight select-none transition-colors",
            textSize,
            theme === "light" ? "text-primary/90" : "text-bg-base",
          )}
        >
          Loji<span className="text-accent font-medium">Next</span>
        </span>
      )}
    </div>
  );
};
