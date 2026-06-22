import { useEffect, useState } from "react";

import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  Award,
  Leaf,
  Minus,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  Trophy,
  X,
} from "lucide-react";

import { Driver } from "../../types";
import { cn } from "../../lib/utils";
import { driverService } from "../../api/drivers";
import { DriverScoreBreakdown } from "./DriverScoreBreakdown";
import { DriverRouteProfile } from "./DriverRouteProfile";
import { useDriversResources } from "../../resources/useResources";

type PerformanceTab = "performance" | "breakdown" | "routes";

interface DriverPerformanceModalProps {
  isOpen: boolean;
  onClose: () => void;
  driver: Driver | null;
}

interface PerformanceData {
  safety_score: number;
  eco_score: number;
  compliance_score: number;
  total_score: number;
  trend: "increasing" | "decreasing" | "stable";
  total_km: number;
  total_trips: number;
}

export function DriverPerformanceModal({
  isOpen,
  onClose,
  driver,
}: DriverPerformanceModalProps) {
  const { driverPerformanceText } = useDriversResources();
  const [data, setData] = useState<PerformanceData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<PerformanceTab>("performance");

  useEffect(() => {
    if (isOpen && driver?.id) {
      setLoading(true);
      setError(null);
      driverService
        .getPerformance(driver.id)
        .then((perf) => setData(perf as PerformanceData))
        .catch((requestError) => {
          console.error("Driver performance request failed:", requestError);
          setError(driverPerformanceText.errorFallback);
        })
        .finally(() => setLoading(false));
    } else {
      setData(null);
    }
    // Modal her yeni sürücü için performans sekmesinden başlasın.
    setActiveTab("performance");
  }, [driver, isOpen]);

  if (!isOpen) {
    return null;
  }

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          className="relative flex w-full max-w-2xl flex-col overflow-hidden rounded-[32px] border border-accent/20 bg-surface/90 shadow-2xl backdrop-blur-xl"
        >
          <div className="flex shrink-0 items-center justify-between border-b border-border bg-elevated/40 p-6">
            <div>
              <h2 className="flex items-center gap-2 text-xl font-bold text-primary">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-accent/40 bg-accent/20 text-accent shadow-sm">
                  <Award className="h-5 w-5" />
                </div>
                {driverPerformanceText.title}
              </h2>
              <p className="mt-1 text-sm text-secondary">
                {driverPerformanceText.subtitle(driver?.ad_soyad ?? "-")}
              </p>
            </div>
            <button
              onClick={onClose}
              className="rounded-full p-2 text-secondary transition-colors hover:bg-elevated hover:text-primary"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="flex shrink-0 gap-1 border-b border-border bg-elevated/20 px-4 pt-3">
            {(["performance", "breakdown", "routes"] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={cn(
                  "rounded-t-card px-4 py-2 text-xs font-bold uppercase tracking-widest transition-all",
                  activeTab === tab
                    ? "border border-b-0 border-border bg-surface text-primary"
                    : "text-secondary hover:text-primary",
                )}
              >
                {driverPerformanceText.tabs[tab]}
              </button>
            ))}
          </div>

          <div className="custom-scrollbar min-h-[400px] overflow-y-auto p-8">
            {activeTab === "breakdown" ? (
              driver?.id ? (
                <DriverScoreBreakdown driverId={driver.id} />
              ) : (
                <p className="text-sm text-secondary text-center">
                  {driverPerformanceText.errorFallback}
                </p>
              )
            ) : activeTab === "routes" ? (
              driver?.id ? (
                <DriverRouteProfile driverId={driver.id} />
              ) : (
                <p className="text-sm text-secondary text-center">
                  {driverPerformanceText.errorFallback}
                </p>
              )
            ) : loading ? (
              <div className="flex h-full flex-col items-center justify-center space-y-4 py-12">
                <div className="h-12 w-12 animate-spin rounded-full border-4 border-accent border-t-transparent" />
                <p className="text-[10px] font-medium uppercase tracking-widest text-secondary">
                  {driverPerformanceText.loading}
                </p>
              </div>
            ) : error ? (
              <div className="flex h-full flex-col items-center justify-center space-y-2 py-12 text-danger">
                <AlertCircle className="h-10 w-10" />
                <p>{error}</p>
              </div>
            ) : data ? (
              <div className="space-y-8">
                <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                  <div className="relative col-span-1 overflow-hidden rounded-[24px] border border-border bg-gradient-to-r from-accent/10 to-success/10 p-6 text-center text-primary shadow-sm md:col-span-3">
                    <div className="absolute right-0 top-0 h-32 w-32 -translate-y-1/2 translate-x-1/2 rounded-full bg-accent/20 blur-[40px]" />
                    <div className="absolute bottom-0 left-0 h-32 w-32 -translate-x-1/4 translate-y-1/2 rounded-full bg-success/10 blur-[40px]" />
                    <div className="relative z-10">
                      <div className="mb-1 text-sm font-bold uppercase tracking-widest text-secondary">
                        {driverPerformanceText.totalScore}
                      </div>
                      <div className="mb-3 text-7xl font-black text-primary drop-shadow-md">
                        {data.total_score}
                      </div>
                      <div className="mx-auto flex w-max items-center justify-center gap-2 rounded-full border border-border bg-surface/40 px-5 py-2 text-sm font-bold shadow-inner">
                        {data.trend === "increasing" && (
                          <TrendingUp className="h-4 w-4 text-success" />
                        )}
                        {data.trend === "decreasing" && (
                          <TrendingDown className="h-4 w-4 text-danger" />
                        )}
                        {data.trend === "stable" && (
                          <Minus className="h-4 w-4 text-warning" />
                        )}
                        <span
                          className={cn(
                            data.trend === "increasing" && "text-success",
                            data.trend === "decreasing" && "text-danger",
                            data.trend === "stable" && "text-warning",
                          )}
                        >
                          {driverPerformanceText.trends[data.trend]}
                        </span>
                      </div>
                    </div>
                  </div>

                  <ScoreCard
                    title={driverPerformanceText.cards.safety}
                    score={data.safety_score}
                    icon={ShieldCheck}
                    color="text-success"
                    bg="bg-success/10 border-success/20"
                  />
                  <ScoreCard
                    title={driverPerformanceText.cards.eco}
                    score={data.eco_score}
                    icon={Leaf}
                    color="text-accent"
                    bg="bg-accent/10 border-accent/20"
                  />
                  <ScoreCard
                    title={driverPerformanceText.cards.compliance}
                    score={data.compliance_score}
                    icon={Trophy}
                    color="text-warning"
                    bg="bg-warning/10 border-warning/20"
                  />
                </div>

                <div className="grid grid-cols-2 gap-6 border-t border-border pt-6">
                  <div className="rounded-[24px] border border-border bg-elevated/40 p-6 text-center shadow-inner">
                    <div className="mb-2 text-4xl font-black text-primary">
                      {data.total_trips}
                    </div>
                    <div className="text-xs font-bold uppercase tracking-wider text-secondary">
                      {driverPerformanceText.stats.trips}
                    </div>
                  </div>
                  <div className="rounded-[24px] border border-border bg-elevated/40 p-6 text-center shadow-inner">
                    <div className="mb-2 text-4xl font-black text-primary">
                      {data.total_km}
                    </div>
                    <div className="text-xs font-bold uppercase tracking-wider text-secondary">
                      {driverPerformanceText.stats.distance}
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}

function ScoreCard({
  title,
  score,
  icon: Icon,
  color,
  bg,
}: {
  title: string;
  score: number;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  bg: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-[24px] border p-6 text-center shadow-sm transition-all hover:scale-[1.02]",
        bg,
      )}
    >
      <div
        className={cn(
          "rounded-xl border border-border bg-surface p-4 shadow-lg",
          color,
        )}
      >
        <Icon className="h-8 w-8" />
      </div>
      <div className="text-sm font-bold uppercase tracking-wider text-secondary">
        {title}
      </div>
      <div className={cn("text-4xl font-black drop-shadow-sm", color)}>
        {score}
      </div>
    </div>
  );
}
