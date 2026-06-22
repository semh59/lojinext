import React from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Info,
  TrendingUp,
  XCircle,
} from "lucide-react";
import { motion } from "framer-motion";

import { fuelComparisonText } from "../../resources/tr/fuel";
import { PredictionComparisonResponse } from "../../types";

interface VehicleOption {
  id: number;
  plaka: string;
}

interface ComparisonWidgetProps {
  data: PredictionComparisonResponse;
  isLoading?: boolean;
  vehicles?: VehicleOption[];
  selectedVehicleId?: number | null;
  onVehicleChange?: (vehicleId: number | null) => void;
}

export const ComparisonWidget: React.FC<ComparisonWidgetProps> = ({
  data,
  isLoading,
  vehicles,
  selectedVehicleId,
  onVehicleChange,
}) => {
  const showVehicleSelect = !!vehicles && !!onVehicleChange;

  const vehicleSelect = showVehicleSelect ? (
    <label className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-secondary">
      <span className="hidden sm:inline">Araç</span>
      <select
        value={selectedVehicleId ?? ""}
        onChange={(e) =>
          onVehicleChange?.(e.target.value ? Number(e.target.value) : null)
        }
        className="rounded-card border border-border bg-elevated px-2 py-1 text-xs font-semibold text-primary focus:border-accent focus:outline-none"
        aria-label="Araç filtresi"
      >
        <option value="">Tüm Filo</option>
        {vehicles!.map((v) => (
          <option key={v.id} value={v.id}>
            {v.plaka}
          </option>
        ))}
      </select>
    </label>
  ) : null;

  if (isLoading) {
    return (
      <div className="h-[400px] w-full rounded-modal border border-border bg-surface/50 animate-pulse" />
    );
  }

  if (!data || data.total_compared === 0) {
    return (
      <div className="flex min-h-[300px] flex-col items-center justify-center rounded-modal border border-border bg-surface p-8 text-center shadow-sm">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-modal border border-border bg-elevated">
          <Activity className="h-8 w-8 text-secondary" />
        </div>
        <h3 className="text-lg font-bold uppercase tracking-widest text-primary">
          {fuelComparisonText.unavailableTitle}
        </h3>
        <p className="mt-2 max-w-[280px] text-sm leading-relaxed text-secondary">
          {fuelComparisonText.unavailableDescription}
        </p>
        {vehicleSelect && <div className="mt-4">{vehicleSelect}</div>}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-1">
        <div className="group relative overflow-hidden rounded-modal border border-info/20 bg-surface p-6 shadow-sm transition-colors hover:border-info/40">
          <div className="absolute right-0 top-0 p-8 opacity-[0.03] transition-opacity group-hover:opacity-[0.06]">
            <TrendingUp className="h-24 w-24 text-info" />
          </div>

          <div className="mb-6 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-info/20 bg-info/10">
              <Activity className="h-5 w-5 text-info" />
            </div>
            <div>
              <h3 className="text-[10px] font-bold uppercase leading-none tracking-widest text-secondary">
                {fuelComparisonText.averageErrorLabel}
              </h3>
              <p className="mt-1 text-lg font-bold text-primary">
                {fuelComparisonText.performanceTitle}
              </p>
            </div>
          </div>

          <div className="relative z-10 space-y-4">
            <div className="flex items-baseline gap-2">
              <span className="text-shadow-sm text-4xl font-bold tracking-tighter text-info tabular-nums">
                {data.mae.toFixed(2)}
              </span>
              <span className="text-[10px] font-bold uppercase tracking-widest text-secondary">
                {fuelComparisonText.maeUnit}
              </span>
            </div>

            <div className="h-2 w-full overflow-hidden rounded-full border border-border bg-elevated">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${Math.max(10, 100 - data.mae * 10)}%` }}
                className="h-full rounded-full bg-info"
              />
            </div>
            <p className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest text-secondary">
              <Info className="h-3.5 w-3.5 text-info" />
              <span className="text-info">
                {fuelComparisonText.rmseValue(data.rmse)}
              </span>
            </p>
          </div>
        </div>

        <div className="relative overflow-hidden rounded-modal border border-border bg-surface p-6 shadow-sm">
          <h3 className="mb-4 text-xs font-bold uppercase tracking-widest text-secondary">
            {fuelComparisonText.accuracyTitle}
          </h3>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <div className="flex justify-between text-[11px] font-bold uppercase transition-colors">
                <span className="flex items-center gap-1.5 text-success">
                  <CheckCircle2 className="h-3 w-3" />
                  {fuelComparisonText.accuracy.good}
                </span>
                <span className="text-primary">
                  {fuelComparisonText.accuracy.tripCount(
                    data.accuracy_distribution.good,
                  )}
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full border border-border bg-elevated">
                <div
                  className="h-full bg-success shadow-sm"
                  style={{ width: `${data.accuracy_distribution.good_pct}%` }}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between text-[11px] font-bold uppercase transition-colors">
                <span className="flex items-center gap-1.5 text-warning">
                  <AlertTriangle className="h-3 w-3" />
                  {fuelComparisonText.accuracy.warning}
                </span>
                <span className="text-primary">
                  {fuelComparisonText.accuracy.tripCount(
                    data.accuracy_distribution.warning,
                  )}
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full border border-border bg-elevated">
                <div
                  className="h-full bg-warning shadow-sm"
                  style={{
                    width: `${data.accuracy_distribution.warning_pct}%`,
                  }}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between text-[11px] font-bold uppercase transition-colors">
                <span className="flex items-center gap-1.5 text-danger">
                  <XCircle className="h-3 w-3" />
                  {fuelComparisonText.accuracy.error}
                </span>
                <span className="text-primary">
                  {fuelComparisonText.accuracy.tripCount(
                    data.accuracy_distribution.error,
                  )}
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full border border-border bg-elevated">
                <div
                  className="h-full bg-danger shadow-sm"
                  style={{ width: `${data.accuracy_distribution.error_pct}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-col rounded-modal border border-border bg-surface p-6 shadow-sm lg:col-span-2">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h3 className="text-[10px] font-bold uppercase leading-none tracking-widest text-secondary">
              {fuelComparisonText.analysisLabel}
            </h3>
            <p className="mt-1 text-lg font-bold text-primary">
              {fuelComparisonText.trendTitle}
            </p>
          </div>
          <div className="flex items-center gap-4">
            {vehicleSelect}
            <div className="flex items-center gap-1.5 rounded-full border border-accent/20 bg-accent/10 px-3 py-1.5">
              <div className="h-2 w-2 rounded-full bg-accent shadow-sm" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-accent">
                {fuelComparisonText.legend.predicted}
              </span>
            </div>
            <div className="flex items-center gap-1.5 rounded-full border border-success/20 bg-success/10 px-3 py-1.5">
              <div className="h-2 w-2 rounded-full bg-success shadow-sm" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-success">
                {fuelComparisonText.legend.actual}
              </span>
            </div>
          </div>
        </div>

        <div className="h-[280px] w-full flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={data.trend}
              margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
            >
              <defs>
                <linearGradient id="colorActual" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="5%"
                    stopColor="var(--success)"
                    stopOpacity={0.2}
                  />
                  <stop
                    offset="95%"
                    stopColor="var(--success)"
                    stopOpacity={0}
                  />
                </linearGradient>
                <linearGradient id="colorPredicted" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="5%"
                    stopColor="var(--accent)"
                    stopOpacity={0.2}
                  />
                  <stop
                    offset="95%"
                    stopColor="var(--accent)"
                    stopOpacity={0}
                  />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke="var(--border)"
                opacity={0.3}
              />
              <XAxis
                dataKey="date"
                axisLine={false}
                tickLine={false}
                tick={{
                  fontSize: 10,
                  fontWeight: 700,
                  fill: "var(--text-secondary)",
                }}
                tickFormatter={(value) =>
                  new Date(value).toLocaleDateString("tr-TR", {
                    day: "numeric",
                    month: "short",
                  })
                }
                opacity={0.5}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{
                  fontSize: 10,
                  fontWeight: 700,
                  fill: "var(--text-secondary)",
                }}
                opacity={0.5}
              />
              <Tooltip
                formatter={(value, _name, item) => [
                  value,
                  item.dataKey === "predicted"
                    ? fuelComparisonText.legend.predicted
                    : fuelComparisonText.legend.actual,
                ]}
                contentStyle={{
                  backgroundColor: "var(--surface)",
                  borderRadius: "12px",
                  border: "1px solid var(--border)",
                  boxShadow: "var(--shadow-lg)",
                  padding: "12px",
                }}
                itemStyle={{
                  color: "var(--text-primary)",
                  fontSize: "12px",
                  fontWeight: 700,
                }}
                labelStyle={{
                  fontSize: "10px",
                  fontWeight: 600,
                  color: "var(--text-secondary)",
                  marginBottom: "4px",
                  textTransform: "uppercase",
                  letterSpacing: "1px",
                }}
              />
              <Area
                type="monotone"
                dataKey="predicted"
                name={fuelComparisonText.legend.predicted}
                stroke="var(--accent)"
                strokeWidth={3}
                fillOpacity={0.1}
                fill="var(--accent)"
              />
              <Area
                type="monotone"
                dataKey="actual"
                name={fuelComparisonText.legend.actual}
                stroke="var(--success)"
                strokeWidth={3}
                fillOpacity={0.1}
                fill="var(--success)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-6 flex items-center gap-3 rounded-modal border border-border bg-elevated/50 p-4">
          <Info className="h-5 w-5 shrink-0 text-secondary" />
          <p className="text-[10px] font-bold uppercase tracking-tight text-secondary">
            {fuelComparisonText.summary(data.total_compared)}{" "}
            <span className="text-primary">
              {fuelComparisonText.summaryHint}
            </span>
          </p>
        </div>
      </div>
    </div>
  );
};
