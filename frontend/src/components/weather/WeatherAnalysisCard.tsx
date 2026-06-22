import React from "react";
import { CloudRain, Wind, Sun } from "lucide-react";
import { cn } from "../../lib/utils";

interface WeatherAnalysisCardProps {
  weatherImpact: number | null;
  weatherLoading: boolean;
}

export const WeatherAnalysisCard: React.FC<WeatherAnalysisCardProps> = ({
  weatherImpact,
  weatherLoading,
}) => {
  if (weatherImpact === null && !weatherLoading) return null;

  const getWeatherDescription = (factor: number) => {
    if (factor > 1.1)
      return {
        text: "Yüksek Tüketim Riski",
        color: "text-danger",
        icon: CloudRain,
      };
    if (factor > 1.02)
      return { text: "Hafif Artış", color: "text-warning", icon: Wind };
    if (factor < 0.98)
      return { text: "Optimal Tasarruf", color: "text-success", icon: Sun };
    return { text: "Normal Koşullar", color: "text-accent", icon: Sun };
  };

  const info = weatherImpact
    ? getWeatherDescription(weatherImpact)
    : { text: "", color: "", icon: Sun };

  return (
    <div
      className={cn(
        "p-4 rounded-2xl border flex items-center justify-between transition-all",
        weatherLoading
          ? "bg-elevated/20 border-border"
          : (weatherImpact || 0) > 1.02
            ? "bg-warning/10 border-warning/20"
            : "bg-success/10 border-success/20",
      )}
    >
      <div className="flex items-center gap-3">
        <div
          className={cn(
            "w-10 h-10 rounded-xl flex items-center justify-center transition-all",
            weatherLoading
              ? "bg-elevated animate-pulse"
              : (weatherImpact || 0) > 1.02
                ? "bg-warning text-bg-base"
                : "bg-success text-bg-base",
          )}
        >
          {weatherLoading ? (
            <Wind className="w-5 h-5 text-secondary" />
          ) : (
            <info.icon className="w-5 h-5" />
          )}
        </div>
        <div>
          <div className="text-[10px] font-black uppercase text-secondary">
            Hava Analizi
          </div>
          <div
            className={cn(
              "text-sm font-bold uppercase",
              weatherLoading ? "text-secondary" : "text-primary",
            )}
          >
            {weatherLoading ? "Hesaplanıyor..." : info.text}
          </div>
        </div>
      </div>
      {!weatherLoading && weatherImpact !== null && (
        <div className="text-right">
          <div className="text-[10px] font-black uppercase text-secondary">
            Etki
          </div>
          <div
            className={cn(
              "text-lg font-black",
              weatherImpact > 1.02 ? "text-warning" : "text-success",
            )}
          >
            {weatherImpact > 1 ? "+" : ""}
            {((weatherImpact - 1) * 100).toFixed(1)}%
          </div>
        </div>
      )}
    </div>
  );
};
