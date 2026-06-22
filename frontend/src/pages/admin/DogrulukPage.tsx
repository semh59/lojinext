import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Target, TrendingUp, Activity, Gauge } from "lucide-react";
import { useTranslation } from "react-i18next";

import ErrorBoundary from "@/components/common/ErrorBoundary";
import { Card } from "@/components/ui/Card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import { adminFuelAccuracyApi, type FuelAccuracyStats } from "@/api/admin";
import { usePageTitle } from "@/hooks/usePageTitle";

const PERIODS = [7, 30, 90] as const;

function fmt(v?: number | null, suffix = ""): string {
  return v === null || v === undefined ? "—" : `${v.toFixed(1)}${suffix}`;
}

function MetricCard({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: typeof Target;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 text-secondary mb-2">
        <Icon size={16} className="text-accent" />
        <span className="text-xs font-bold uppercase tracking-wider">
          {label}
        </span>
      </div>
      <p className="text-2xl font-bold text-primary">{value}</p>
      {hint && <p className="text-xs text-tertiary mt-1">{hint}</p>}
    </Card>
  );
}

export default function DogrulukPage() {
  const { t } = useTranslation();
  usePageTitle(t("admin.forecast_accuracy", "Forecast Accuracy"));
  const [days, setDays] = useState<number>(30);

  const { data, isLoading } = useQuery<FuelAccuracyStats>({
    queryKey: ["fuelAccuracy", days],
    queryFn: () => adminFuelAccuracyApi.get(days),
    staleTime: 5 * 60 * 1000,
  });

  return (
    <ErrorBoundary>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Target className="text-accent" size={24} />
            <div>
              <h1 className="text-xl font-bold text-primary">
                {t("admin.accuracy_title", "Fuel Forecast Accuracy")}
              </h1>
              <p className="text-sm text-secondary">
                {t(
                  "admin.accuracy_subtitle",
                  "MAPE / RMSE / bias — completed trips (forecast vs actual)",
                )}
              </p>
            </div>
          </div>
          <div className="flex gap-1 rounded-card border border-border bg-surface p-1">
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setDays(p)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-card transition-colors ${
                  days === p
                    ? "bg-accent text-white"
                    : "text-secondary hover:text-primary"
                }`}
              >
                {t("admin.accuracy_days", "{{n}} days", { n: p })}
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <div className="flex h-48 items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-accent border-t-transparent" />
          </div>
        ) : !data || data.sample_size === 0 ? (
          <Card className="p-10 text-center text-secondary">
            {t(
              "admin.accuracy_no_data",
              "Not enough data for forecast/actual comparison in the selected period.",
            )}
          </Card>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard
                icon={Target}
                label="MAPE"
                value={fmt(data.mape_pct, "%")}
                hint={t(
                  "admin.accuracy_mape_hint",
                  "Avg. absolute percentage error (lower = better)",
                )}
              />
              <MetricCard
                icon={Gauge}
                label="RMSE"
                value={fmt(data.rmse_l_100km, " L/100km")}
              />
              <MetricCard
                icon={TrendingUp}
                label={t("admin.accuracy_bias_label", "Bias")}
                value={fmt(data.bias_pct, "%")}
                hint={t("admin.accuracy_bias_hint", "Prediction − Actual")}
              />
              <MetricCard
                icon={Activity}
                label={t("admin.accuracy_coverage_label", "Coverage")}
                value={fmt(data.coverage_pct, "%")}
                hint={t("admin.accuracy_coverage_hint", "{{n}} trip sample", {
                  n: data.sample_size,
                })}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <MetricCard
                icon={Gauge}
                label={t("admin.accuracy_mean_predicted", "Average Forecast")}
                value={fmt(data.mean_predicted, " L/100km")}
              />
              <MetricCard
                icon={Gauge}
                label={t("admin.accuracy_actual_avg", "Average Actual")}
                value={fmt(data.mean_actual, " L/100km")}
              />
            </div>

            <Card className="p-0 overflow-hidden">
              <div className="border-b border-border bg-elevated/50 p-4">
                <h2 className="text-base font-bold text-primary">
                  {t("admin.accuracy_vehicle_section", "Vehicle Breakdown")}
                </h2>
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>
                      {t("admin.accuracy_col_vehicle", "Vehicle")}
                    </TableHead>
                    <TableHead>
                      {t("admin.accuracy_col_sample", "Sample")}
                    </TableHead>
                    <TableHead>MAPE</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.breakdown_by_arac.length === 0 ? (
                    <TableRow>
                      <TableCell
                        colSpan={3}
                        className="text-center text-secondary"
                      >
                        {t(
                          "admin.accuracy_no_breakdown",
                          "No vehicle breakdown",
                        )}
                      </TableCell>
                    </TableRow>
                  ) : (
                    data.breakdown_by_arac.map((a) => (
                      <TableRow key={a.arac_id}>
                        <TableCell className="font-medium text-primary">
                          {a.plaka || `#${a.arac_id}`}
                        </TableCell>
                        <TableCell>{a.sample_size}</TableCell>
                        <TableCell>{fmt(a.mape_pct, "%")}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </Card>
          </>
        )}
      </div>
    </ErrorBoundary>
  );
}
