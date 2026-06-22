import { useEffect, useMemo, useState } from "react";

import { AnimatePresence, motion } from "framer-motion";
import { Save, Star, TrendingUp, X } from "lucide-react";

import { Driver } from "../../types";
import { useDriversResources } from "../../resources/useResources";
interface DriverScoreModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (score: number) => Promise<void>;
  driver: Driver | null;
}

const calculateHybridScore = (
  currentHybrid: number,
  newManual: number,
  oldManual: number,
): number => {
  const estimatedPerformance = (currentHybrid - 0.4 * oldManual) / 0.6;
  const newHybrid = 0.6 * estimatedPerformance + 0.4 * newManual;
  return Math.max(0.1, Math.min(2.0, newHybrid));
};

const scoreToStars = (score: number): number => {
  if (score >= 1.8) return 5;
  if (score >= 1.5) return 4;
  if (score >= 1.2) return 3;
  if (score >= 0.8) return 2;
  return 1;
};

export function DriverScoreModal({
  isOpen,
  onClose,
  onSave,
  driver,
}: DriverScoreModalProps) {
  const { driverScoreText } = useDriversResources();
  const getScoreLabel = (
    score: number,
  ): { label: string; color: string; bg: string } => {
    if (score >= 1.8) {
      return {
        label: driverScoreText.levels.excellent,
        color: "var(--success)",
        bg: "rgba(var(--success-rgb), 0.1)",
      };
    }
    if (score >= 1.5) {
      return {
        label: driverScoreText.levels.good,
        color: "rgba(var(--accent-rgb), 1)",
        bg: "rgba(var(--accent-rgb), 0.1)",
      };
    }
    if (score >= 1.2) {
      return {
        label: driverScoreText.levels.medium,
        color: "var(--warning)",
        bg: "rgba(var(--warning-rgb), 0.1)",
      };
    }
    if (score >= 0.8) {
      return {
        label: driverScoreText.levels.low,
        color: "var(--danger)",
        bg: "rgba(var(--danger-rgb), 0.1)",
      };
    }
    return {
      label: driverScoreText.levels.veryLow,
      color: "var(--danger)",
      bg: "rgba(var(--danger-rgb), 0.1)",
    };
  };
  const [score, setScore] = useState(1.0);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (driver) {
      setScore(driver.manual_score || 1.0);
    }
  }, [driver, isOpen]);

  const estimatedHybrid = useMemo(() => {
    if (!driver) {
      return score;
    }
    return calculateHybridScore(
      driver.score || 1.0,
      score,
      driver.manual_score || 1.0,
    );
  }, [driver, score]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!driver?.id) {
      return;
    }

    setIsLoading(true);
    try {
      await onSave(score);
      onClose();
    } catch (saveError) {
      console.error("Score update failed:", saveError);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen || !driver) {
    return null;
  }

  const currentLabel = getScoreLabel(driver.score || 1.0);
  const newLabel = getScoreLabel(estimatedHybrid);
  const stars = scoreToStars(estimatedHybrid);
  const scoreChange = estimatedHybrid - (driver.score || 1.0);

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          className="flex w-full max-w-md flex-col overflow-hidden rounded-[12px] border border-border bg-surface shadow-xl"
        >
          <div className="relative shrink-0 border-b border-border bg-elevated/30 p-6 text-primary">
            <button
              onClick={onClose}
              className="absolute right-4 top-4 rounded-full p-2 text-secondary transition-colors hover:bg-elevated hover:text-primary"
            >
              <X className="h-5 w-5" />
            </button>
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-[10px] border border-border bg-elevated shadow-sm">
                <Star className="h-7 w-7 fill-accent/20 text-accent" />
              </div>
              <div>
                <h2 className="text-xl font-bold tracking-tight text-primary">
                  {driverScoreText.title}
                </h2>
                <p className="text-xs font-medium text-secondary">
                  {driver.ad_soyad}
                </p>
              </div>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6 p-6">
            <div className="rounded-[10px] border border-border bg-elevated/20 p-4">
              <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-secondary">
                {driverScoreText.sections.current}
              </p>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-2xl font-bold text-primary">
                    {(driver.score || 1.0).toFixed(2)}
                  </span>
                  <span
                    className="shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold"
                    style={{
                      backgroundColor: currentLabel.bg,
                      color: currentLabel.color,
                      borderColor: `${currentLabel.color}30`,
                    }}
                  >
                    {currentLabel.label}
                  </span>
                </div>
                <div className="text-right text-[10px] font-bold uppercase tracking-tight text-secondary">
                  <p>
                    {driverScoreText.labels.currentManual(
                      driver.manual_score || 1.0,
                    )}
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold uppercase tracking-widest text-secondary">
                  {driverScoreText.sections.manual}
                </label>
                <span className="text-2xl font-bold text-accent">
                  {score.toFixed(1)}
                </span>
              </div>

              <input
                type="range"
                min="0.1"
                max="2.0"
                step="0.1"
                value={score}
                onChange={(event) => setScore(parseFloat(event.target.value))}
                className="h-3 w-full cursor-pointer appearance-none rounded-lg bg-elevated accent-accent shadow-inner"
                style={{
                  background:
                    "linear-gradient(to right, var(--danger), var(--warning), var(--success))",
                }}
              />

              <div className="flex items-center justify-between text-[10px] font-black uppercase tracking-wider">
                <span className="rounded-lg border border-danger/20 bg-danger/10 px-3 py-1.5 text-danger">
                  {driverScoreText.scoreBands.risk}
                </span>
                <span className="rounded-lg border border-warning/20 bg-warning/10 px-3 py-1.5 text-warning">
                  {driverScoreText.scoreBands.neutral}
                </span>
                <span className="rounded-lg border border-success/20 bg-success/10 px-3 py-1.5 text-success">
                  {driverScoreText.scoreBands.excellent}
                </span>
              </div>
            </div>

            <div className="rounded-[10px] border border-accent/10 bg-accent/5 p-4">
              <div className="mb-3 flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-accent" />
                <p className="text-[10px] font-bold uppercase tracking-widest text-accent">
                  {driverScoreText.sections.estimated}
                </p>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-3xl font-bold text-primary">
                    {estimatedHybrid.toFixed(2)}
                  </span>
                  <div className="flex items-center gap-0.5">
                    {[1, 2, 3, 4, 5].map((index) => (
                      <Star
                        key={index}
                        className={`h-4 w-4 ${
                          index <= stars
                            ? "fill-warning text-warning"
                            : "text-border"
                        }`}
                      />
                    ))}
                  </div>
                </div>
                <div className="text-right">
                  <span
                    className="shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold"
                    style={{
                      backgroundColor: newLabel.bg,
                      color: newLabel.color,
                      borderColor: `${newLabel.color}30`,
                    }}
                  >
                    {newLabel.label}
                  </span>
                  {scoreChange !== 0 && (
                    <p
                      className={`mt-1 text-[10px] font-bold uppercase tracking-tight ${
                        scoreChange > 0 ? "text-success" : "text-danger"
                      }`}
                    >
                      {scoreChange > 0 ? "+" : ""}
                      {scoreChange.toFixed(2)}
                    </p>
                  )}
                </div>
              </div>
              <p className="mt-2 text-[9px] font-medium text-secondary/60">
                {driverScoreText.labels.hybridFormula}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="h-11 rounded-[8px] border border-border bg-elevated text-xs font-bold text-primary transition-colors hover:bg-elevated/70"
              >
                {driverScoreText.actions.cancel}
              </button>
              <button
                type="submit"
                disabled={isLoading}
                className="flex h-11 items-center justify-center gap-2 rounded-[8px] bg-accent text-xs font-bold text-bg-base shadow-sm shadow-accent/20 transition-all hover:bg-accent/90 disabled:opacity-50"
              >
                {isLoading ? (
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-bg-base/30 border-t-bg-base" />
                ) : (
                  <>
                    <Save className="h-3.5 w-3.5" />
                    {driverScoreText.actions.update}
                  </>
                )}
              </button>
            </div>
          </form>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
