import { motion } from "framer-motion";
import { LucideIcon } from "lucide-react";

import { tripStatsText } from "../../resources/tr/trips";
import { cn } from "../../lib/utils";

interface TripStat {
  label: string;
  value: string | number;
  icon: LucideIcon;
  color: string;
  bg: string;
  unit?: string;
}

interface TripStatsProps {
  stats: TripStat[];
}

const colorMap = [
  {
    text: "text-info",
    bg: "bg-info/10",
    glow: "bg-info/5",
    accent: "border-info/20",
  },
  {
    text: "text-success",
    bg: "bg-success/10",
    glow: "bg-success/5",
    accent: "border-success/20",
  },
  {
    text: "text-danger",
    bg: "bg-danger/10",
    glow: "bg-danger/5",
    accent: "border-danger/20",
  },
  {
    text: "text-warning",
    bg: "bg-warning/10",
    glow: "bg-warning/5",
    accent: "border-warning/20",
  },
  {
    text: "text-secondary",
    bg: "bg-secondary/10",
    glow: "bg-secondary/5",
    accent: "border-secondary/20",
  },
];

export function TripStats({ stats }: TripStatsProps) {
  return (
    <div className="mb-8">
      <div className="mb-6 flex flex-col gap-1">
        <h2 className="text-sm font-black uppercase tracking-[0.2em] text-tertiary">
          {tripStatsText.heading}
        </h2>
      </div>

      <div
        className={cn(
          "grid grid-cols-1 gap-6 md:grid-cols-2",
          stats.length >= 5 ? "lg:grid-cols-5" : "lg:grid-cols-4",
        )}
      >
        {stats.map((stat, index) => {
          const theme = colorMap[index % colorMap.length];

          return (
            <motion.div
              key={`${stat.label}-${index}`}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: 0.5,
                delay: index * 0.05,
                ease: "easeOut",
              }}
              className={cn(
                "glass relative overflow-hidden rounded-modal border border-border/40 p-6 transition-all hover:border-accent/30 hover:shadow-xl hover:shadow-accent/5",
              )}
            >
              <div
                className={cn(
                  "absolute -bottom-2 -right-2 h-24 w-24 rounded-full blur-[40px] opacity-20 transition-all group-hover:opacity-40",
                  theme.glow,
                )}
              />

              <div className="relative z-10 flex items-start justify-between">
                <div className="space-y-3">
                  <p className="text-[10px] font-black uppercase tracking-widest text-tertiary">
                    {stat.label}
                  </p>
                  <div className="flex items-baseline gap-1.5">
                    <h3 className="text-2xl font-black tracking-tight text-primary tabular-nums">
                      {typeof stat.value === "number" && index !== 1
                        ? stat.value.toLocaleString("tr-TR")
                        : stat.value}
                    </h3>
                    {stat.unit && (
                      <span className="mb-0.5 text-[10px] font-black uppercase tracking-tighter text-secondary">
                        {stat.unit}
                      </span>
                    )}
                  </div>
                </div>

                <div
                  className={cn(
                    "flex h-12 w-12 items-center justify-center rounded-xl transition-all duration-300 group-hover:scale-110 group-hover:rotate-6",
                    theme.bg,
                    theme.text,
                  )}
                >
                  <stat.icon size={22} strokeWidth={2.5} />
                </div>
              </div>

              <div className="absolute bottom-0 left-0 h-[2px] w-full bg-border/20">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: "100%" }}
                  transition={{ duration: 1.5, delay: index * 0.2 }}
                  className={cn(
                    "h-full opacity-50",
                    theme.text.replace("text-", "bg-"),
                  )}
                />
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
