import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/Card";
import { Lightbulb, Loader2, AlertCircle } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { chartTheme } from "@/lib/chart-theme";
import { predictionService } from "@/api/predictions";
import type { PredictionRequest } from "@/types";
import { useTranslation } from "react-i18next";

interface XaiExplainPanelProps {
  request: PredictionRequest;
}

/** components objesini sıralı bar veri noktasına dönüştürür. */
function toBars(components: Record<string, number> | undefined | null) {
  if (!components) return [];
  return Object.entries(components)
    .map(([feature, value]) => ({
      feature,
      // bazı backend'ler oran (0..1), bazıları yüzde döner — normalize ediyoruz.
      value: Math.abs(value) > 1 ? value : value * 100,
    }))
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .slice(0, 10);
}

export function XaiExplainPanel({ request }: XaiExplainPanelProps) {
  const { t } = useTranslation();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["xai-explain", request],
    queryFn: () => predictionService.explain(request),
    enabled: request.arac_id > 0 && request.mesafe_km > 0,
    staleTime: 60 * 1000,
  });

  const bars = toBars(
    (data as any)?.components as Record<string, number> | undefined,
  );

  return (
    <Card padding="lg" className="space-y-4">
      <div className="flex items-center gap-2">
        <Lightbulb className="h-5 w-5 text-warning" />
        <h3 className="text-sm font-semibold text-primary">
          {t("predictions.xai_panel_title")}
        </h3>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 py-6 text-secondary">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm">{t("predictions.xai_panel_loading")}</span>
        </div>
      ) : isError ? (
        <div className="flex items-center gap-2 rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          <AlertCircle className="h-4 w-4" />
          {t("predictions.xai_panel_error")}
        </div>
      ) : bars.length === 0 ? (
        <p className="text-sm text-secondary">
          {t("predictions.xai_panel_no_components")}
        </p>
      ) : (
        <>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={bars}
                layout="vertical"
                margin={{ top: 4, right: 16, left: 0, bottom: 0 }}
              >
                <CartesianGrid {...chartTheme.grid} />
                <XAxis
                  type="number"
                  tick={chartTheme.tickSmall}
                  axisLine={false}
                  tickLine={false}
                  unit=" %"
                />
                <YAxis
                  type="category"
                  dataKey="feature"
                  tick={chartTheme.tickSmall}
                  axisLine={false}
                  tickLine={false}
                  width={120}
                />
                <Tooltip
                  {...chartTheme.tooltip}
                  formatter={(value) => [
                    `${Number(value ?? 0).toFixed(1)}%`,
                    t("predictions.xai_panel_impact"),
                  ]}
                />
                <Bar
                  dataKey="value"
                  fill={chartTheme.colors.accent}
                  radius={[0, 6, 6, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[11px] text-secondary">
            {t("predictions.xai_panel_footnote")}
          </p>
        </>
      )}
    </Card>
  );
}
