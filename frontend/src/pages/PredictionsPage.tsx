import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, BrainCircuit, CalendarRange } from "lucide-react";
import { useTranslation } from "react-i18next";
import { MetricCards } from "@/components/predictions/MetricCards";
import { EnsembleStatusCard } from "@/components/predictions/EnsembleStatusCard";
import { AccuracyChart } from "@/components/predictions/AccuracyChart";
import { PredictionSimulator } from "@/components/predictions/PredictionSimulator";
import { TimeSeriesForecast } from "@/components/predictions/TimeSeriesForecast";
import { TimeSeriesStatusCard } from "@/components/predictions/TimeSeriesStatusCard";
import { TimeSeriesTrendSection } from "@/components/predictions/TimeSeriesTrendSection";
import { predictionService } from "@/api/predictions";

type Tab = "overview" | "simulator" | "timeseries";

export default function PredictionsPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  const TABS: Array<{ id: Tab; label: string; icon: typeof BarChart3 }> = [
    {
      id: "overview",
      label: t("predictions.tab_overview", "Overview"),
      icon: BarChart3,
    },
    {
      id: "simulator",
      label: t("predictions.tab_simulator", "Trip Simulation"),
      icon: BrainCircuit,
    },
    {
      id: "timeseries",
      label: t("predictions.tab_timeseries", "Time Series"),
      icon: CalendarRange,
    },
  ];

  const { data: ensemble } = useQuery({
    queryKey: ["predictions-ensemble"],
    queryFn: () => predictionService.getEnsembleStatus(),
    staleTime: 5 * 60 * 1000,
    enabled: activeTab === "overview",
  });

  const { data: comparison } = useQuery({
    queryKey: ["predictions-comparison"],
    queryFn: () => predictionService.getComparison(30),
    staleTime: 10 * 60 * 1000,
    enabled: activeTab === "overview",
  });

  return (
    <div data-testid="predictions-page" className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-primary">
          {t("predictions.page_title", "ML Predictions")}
        </h1>
        <p className="text-sm text-secondary">
          {t(
            "predictions.page_subtitle",
            "Model performance, trip simulation, and time series forecasts",
          )}
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-border">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`relative flex items-center gap-2 px-4 py-2.5 text-sm font-semibold transition-colors border-b-2 -mb-px ${
              activeTab === id
                ? "border-accent text-accent"
                : "border-transparent text-secondary hover:text-primary"
            }`}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>

      {activeTab === "overview" && (
        <>
          {comparison && (
            <MetricCards
              mae={comparison.mae}
              rmse={comparison.rmse}
              totalCompared={comparison.total_compared}
              goodPct={comparison.accuracy_distribution.good_pct}
            />
          )}

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {ensemble && <EnsembleStatusCard data={ensemble} />}
            <AccuracyChart data={comparison?.trend ?? []} />
          </div>
        </>
      )}

      {activeTab === "simulator" && <PredictionSimulator />}

      {activeTab === "timeseries" && (
        <div className="space-y-6">
          <TimeSeriesStatusCard />
          <TimeSeriesForecast />
          <TimeSeriesTrendSection days={30} />
        </div>
      )}
    </div>
  );
}
