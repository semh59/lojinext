import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { PiggyBank, Target, TrendingUp } from "lucide-react";

import { reportsApi } from "@/services/api";
import { RoiStats } from "../../types";
import { useReportsResources } from "../../resources/useResources";
import { useLocale } from "../../hooks/useLocale";

type SavingsStats = {
  current_consumption: number;
  target_consumption: number;
  current_cost: number;
  target_cost: number;
  potential_savings: number;
  savings_percentage: number;
  annual_projection: number;
};

const TARGET_CONSUMPTION = 28;

export function ROICalculator() {
  const { reportRoiText } = useReportsResources();
  const locale = useLocale();
  const [investment, setInvestment] = useState(50000);
  const [roiStats, setRoiStats] = useState<RoiStats | null>(null);
  const [savingsStats, setSavingsStats] = useState<SavingsStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [roiError, setRoiError] = useState<string | null>(null);
  const [savingsError, setSavingsError] = useState<string | null>(null);

  useEffect(() => {
    const fetchReportData = async () => {
      setLoading(true);
      setRoiError(null);
      setSavingsError(null);

      const [roiResult, savingsResult] = await Promise.allSettled([
        reportsApi.getRoiStats(investment, TARGET_CONSUMPTION),
        reportsApi.getSavingsPotential(TARGET_CONSUMPTION),
      ]);

      if (roiResult.status === "fulfilled") {
        setRoiStats(roiResult.value);
      } else {
        console.error("ROI analysis request failed:", roiResult.reason);
        setRoiStats(null);
        setRoiError(reportRoiText.roiUnavailable);
      }

      if (savingsResult.status === "fulfilled") {
        setSavingsStats(savingsResult.value as SavingsStats);
      } else {
        console.error("Savings analysis request failed:", savingsResult.reason);
        setSavingsStats(null);
        setSavingsError(reportRoiText.savingsUnavailable);
      }

      setLoading(false);
    };

    const timer = setTimeout(fetchReportData, 400);
    return () => clearTimeout(timer);
  }, [
    investment,
    reportRoiText.roiUnavailable,
    reportRoiText.savingsUnavailable,
  ]);

  const formatCurrency = (value: number) =>
    new Intl.NumberFormat(locale, {
      style: "currency",
      currency: "TRY",
      maximumFractionDigits: 0,
    }).format(value);

  const renderErrorBox = (message: string) => (
    <div className="rounded-2xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
      {message}
    </div>
  );

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: loading ? 0.65 : 1, x: 0 }}
        className="space-y-8 rounded-2xl border border-border bg-surface p-6 shadow-sm lg:p-8"
      >
        <div>
          <h3 className="mb-2 text-xl font-bold text-primary">
            {reportRoiText.title}
          </h3>
          <p className="text-sm text-secondary">{reportRoiText.description}</p>
        </div>

        {roiError && renderErrorBox(roiError)}
        {savingsError && renderErrorBox(savingsError)}

        <div className="space-y-4">
          <div className="flex items-center justify-between text-sm font-bold">
            <span className="text-secondary">
              {reportRoiText.investmentAmount}
            </span>
            <span className="text-primary">{formatCurrency(investment)}</span>
          </div>
          <input
            type="range"
            min="10000"
            max="500000"
            step="5000"
            value={investment}
            onChange={(event) => setInvestment(Number(event.target.value))}
            className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-border accent-primary"
          />
          <div className="flex justify-between text-xs font-bold uppercase text-secondary">
            <span>{reportRoiText.rangeMin}</span>
            <span>{reportRoiText.rangeMax}</span>
          </div>
        </div>

        <div className="rounded-2xl border border-info/20 bg-info/10 p-6">
          <div className="flex items-start gap-3">
            <Target className="mt-1 h-5 w-5 text-info" />
            <div>
              <h4 className="mb-1 text-sm font-bold text-info">
                {reportRoiText.targetConsumptionTitle}
              </h4>
              <p className="text-xs text-info/80">
                {savingsStats ? (
                  <>
                    {reportRoiText.targetConsumptionPrefix}{" "}
                    <b className="text-info">
                      {savingsStats.current_consumption} L/100km
                    </b>{" "}
                    {reportRoiText.targetConsumptionMiddle}{" "}
                    <b className="text-info">
                      {savingsStats.target_consumption} L/100km
                    </b>{" "}
                    {reportRoiText.targetConsumptionSuffix}
                  </>
                ) : (
                  reportRoiText.targetConsumptionUnavailable
                )}
              </p>
            </div>
          </div>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        className="space-y-6"
      >
        <div className="group relative flex items-center justify-between overflow-hidden rounded-[32px] border border-border bg-surface p-8 shadow-sm">
          <div className="absolute inset-0 bg-gradient-to-r from-info/10 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
          <div className="relative z-10">
            <p className="mb-1 text-xs font-black uppercase text-secondary">
              {reportRoiText.monthlyPotential}
            </p>
            <h3 className="text-3xl font-black text-info">
              {savingsStats
                ? formatCurrency(savingsStats.potential_savings / 3)
                : "-"}
            </h3>
          </div>
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-info/10 text-info">
            <TrendingUp className="h-6 w-6" />
          </div>
        </div>

        <div className="group relative flex items-center justify-between overflow-hidden rounded-[32px] border border-border bg-surface p-8 shadow-sm">
          <div className="absolute inset-0 bg-gradient-to-r from-success/10 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
          <div className="relative z-10">
            <p className="mb-1 text-xs font-black uppercase text-secondary">
              {reportRoiText.annualSavings}
            </p>
            <h3 className="text-3xl font-black text-success">
              {savingsStats
                ? formatCurrency(savingsStats.annual_projection)
                : "-"}
            </h3>
          </div>
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-success/10 text-success">
            <PiggyBank className="h-6 w-6" />
          </div>
        </div>

        <div className="group relative flex items-center justify-between overflow-hidden rounded-[32px] border border-border bg-surface p-8 shadow-sm">
          <div className="absolute inset-0 bg-gradient-to-r from-accent/10 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
          <div className="relative z-10">
            <p className="mb-1 text-xs font-black uppercase text-secondary">
              {reportRoiText.roiMetricTitle}
            </p>
            <h3 className="text-3xl font-black text-accent">
              {roiStats ? `%${roiStats.annual_roi_percentage.toFixed(0)}` : "-"}
            </h3>
            {!roiStats && (
              <p className="mt-2 text-xs text-secondary">
                {reportRoiText.roiMetricUnavailable}
              </p>
            )}
          </div>
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent/10 text-accent">
            <TrendingUp className="h-6 w-6" />
          </div>
        </div>

        {roiStats && roiStats.annual_roi_percentage > 100 && (
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="rounded-2xl bg-gradient-to-r from-accent to-accent/80 p-4 text-center text-accent-content shadow-sm"
          >
            <p className="text-sm font-bold">
              {reportRoiText.strongImpactMessage(roiStats.payback_months)}
            </p>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}
