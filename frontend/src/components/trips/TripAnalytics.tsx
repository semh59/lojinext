import { motion } from "framer-motion";
import { Activity, AlertTriangle, Gauge, Info, TrendingUp } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { FuelPerformanceAnalyticsResponse } from "../../types";
import { cn } from "../../lib/utils";
import { Skeleton } from "../ui/Skeleton";
import { useTripsResources } from "../../resources/useResources";

interface TripAnalyticsProps {
  data?: FuelPerformanceAnalyticsResponse;
  isLoading?: boolean;
}

export function TripAnalytics({ data, isLoading = false }: TripAnalyticsProps) {
  const { tripAnalyticsText } = useTripsResources();
  if (isLoading) {
    return (
      <div className="mb-8 space-y-6">
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
          {[...Array(4)].map((_, index) => (
            <Skeleton key={index} className="h-28 rounded-2xl" />
          ))}
        </div>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <Skeleton className="h-[350px] rounded-[32px]" />
          <Skeleton className="h-[350px] rounded-[32px]" />
        </div>
      </div>
    );
  }

  if (!data || data.low_data || data.kpis.total_compared < 3) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="glass mb-10 flex flex-col items-center rounded-[40px] border border-border/40 p-16 text-center"
      >
        <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-accent/5 text-accent/40 animate-pulse">
          <Activity size={40} />
        </div>
        <h3 className="text-xl font-black uppercase tracking-wider text-primary">
          {tripAnalyticsText.insufficientTitle}
        </h3>
        <p className="mt-3 max-w-sm text-sm font-medium leading-relaxed text-secondary">
          {tripAnalyticsText.insufficientDescription}
        </p>
      </motion.div>
    );
  }

  const distributionData = [
    {
      name: tripAnalyticsText.distribution.good,
      value: data.distribution.good,
      color: "var(--success)",
    },
    {
      name: tripAnalyticsText.distribution.warning,
      value: data.distribution.warning,
      color: "var(--warning)",
    },
    {
      name: tripAnalyticsText.distribution.error,
      value: data.distribution.error,
      color: "var(--danger)",
    },
  ];

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="min-w-[140px] rounded-2xl border border-border bg-surface/90 p-4 shadow-2xl backdrop-blur-md">
          <p className="mb-3 border-b border-border pb-2 text-[10px] font-black uppercase tracking-widest text-tertiary">
            {label}
          </p>
          <div className="space-y-2">
            {payload.map((entry: any, index: number) => (
              <div
                key={`${entry.name}-${index}`}
                className="flex items-center justify-between gap-4"
              >
                <div className="flex items-center gap-2">
                  <div
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ backgroundColor: entry.color }}
                  />
                  <span className="text-[10px] font-black uppercase tracking-tighter text-secondary">
                    {entry.name}
                  </span>
                </div>
                <span className="text-xs font-black text-primary tabular-nums">
                  {entry.value.toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        </div>
      );
    }

    return null;
  };

  const kpis = [
    {
      label: tripAnalyticsText.kpis.mae.label,
      value: data.kpis.mae.toFixed(2),
      description: tripAnalyticsText.kpis.mae.description,
      icon: Activity,
      color: "text-accent",
    },
    {
      label: tripAnalyticsText.kpis.rmse.label,
      value: data.kpis.rmse.toFixed(2),
      description: tripAnalyticsText.kpis.rmse.description,
      icon: Gauge,
      color: "text-accent",
    },
    {
      label: tripAnalyticsText.kpis.compared.label,
      value: data.kpis.total_compared,
      description: tripAnalyticsText.kpis.compared.description,
      icon: TrendingUp,
      color: "text-success",
    },
    {
      label: tripAnalyticsText.kpis.highDeviation.label,
      value: `%${data.kpis.high_deviation_ratio.toFixed(1)}`,
      description: tripAnalyticsText.kpis.highDeviation.description,
      icon: AlertTriangle,
      color: "text-danger",
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      className="mb-10 space-y-8 overflow-hidden"
    >
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
        {kpis.map((kpi) => (
          <div
            key={kpi.label}
            className="glass rounded-2xl border border-border/40 p-5 transition-all hover:border-accent/30"
          >
            <div className="mb-3 flex items-center justify-between">
              <span className="text-[10px] font-black uppercase tracking-[0.15em] text-tertiary">
                {kpi.label}
              </span>
              <kpi.icon size={14} className={cn("opacity-40", kpi.color)} />
            </div>
            <div className={cn("text-2xl font-black tabular-nums", kpi.color)}>
              {kpi.value}
            </div>
            <p className="mt-2 text-[10px] font-bold leading-tight text-tertiary">
              {kpi.description}
            </p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-2">
        <div className="glass flex h-[400px] flex-col rounded-[32px] border border-border/40 p-8">
          <div className="mb-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/5 text-accent">
                <TrendingUp size={20} />
              </div>
              <div>
                <h4 className="text-sm font-black uppercase tracking-tight text-primary">
                  {tripAnalyticsText.trend.title}
                </h4>
                <p className="text-[10px] font-bold text-tertiary">
                  {tripAnalyticsText.trend.description}
                </p>
              </div>
            </div>
          </div>
          <div className="flex-1 rounded-2xl border border-border/20 bg-elevated p-4">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={data.trend}
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--border)"
                  opacity={0.2}
                  vertical={false}
                />
                <XAxis dataKey="date" hide />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{
                    fill: "var(--text-tertiary)",
                    fontSize: 10,
                    fontWeight: 800,
                  }}
                />
                <Tooltip
                  content={<CustomTooltip />}
                  cursor={{
                    stroke: "var(--accent)",
                    strokeWidth: 1,
                    strokeDasharray: "4 4",
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="predicted"
                  stroke="var(--accent)"
                  strokeWidth={3}
                  dot={false}
                  name={tripAnalyticsText.trend.predicted}
                />
                <Line
                  type="monotone"
                  dataKey="actual"
                  stroke="var(--success)"
                  strokeWidth={3}
                  dot={false}
                  name={tripAnalyticsText.trend.actual}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="glass flex h-[400px] flex-col rounded-[32px] border border-border/40 p-8">
          <div className="mb-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-warning/5 text-warning">
                <Gauge size={20} />
              </div>
              <div>
                <h4 className="text-sm font-black uppercase tracking-tight text-primary">
                  {tripAnalyticsText.distribution.title}
                </h4>
                <p className="text-[10px] font-bold text-tertiary">
                  {tripAnalyticsText.distribution.description}
                </p>
              </div>
            </div>
          </div>
          <div className="flex-1 rounded-2xl border border-border/20 bg-elevated p-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={distributionData}
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--border)"
                  opacity={0.2}
                  vertical={false}
                />
                <XAxis
                  dataKey="name"
                  axisLine={false}
                  tickLine={false}
                  tick={{
                    fill: "var(--text-tertiary)",
                    fontSize: 10,
                    fontWeight: 900,
                  }}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{
                    fill: "var(--text-tertiary)",
                    fontSize: 10,
                    fontWeight: 800,
                  }}
                />
                <Tooltip
                  cursor={{ fill: "transparent" }}
                  content={<CustomTooltip />}
                />
                <Bar dataKey="value" radius={[12, 12, 0, 0]}>
                  {distributionData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="glass rounded-[32px] border border-border/40 p-8">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-danger/5 text-danger">
            <AlertTriangle size={20} />
          </div>
          <div>
            <h4 className="text-sm font-black uppercase tracking-tight text-primary">
              {tripAnalyticsText.outliers.title}
            </h4>
            <p className="text-[10px] font-bold text-tertiary">
              {tripAnalyticsText.outliers.description}
            </p>
          </div>
        </div>
        <div className="grid max-h-[350px] grid-cols-1 gap-3 overflow-y-auto pr-2 custom-scrollbar lg:grid-cols-2">
          {data.outliers.map((item) => (
            <div
              key={item.id}
              className="group flex items-center justify-between rounded-2xl border border-border/40 bg-elevated p-4 transition-all hover:bg-surface"
            >
              <div className="flex min-w-0 items-center gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-danger/5 transition-transform group-hover:scale-110">
                  <Info size={16} className="text-danger" />
                </div>
                <div>
                  <div className="truncate text-sm font-bold leading-tight text-primary">
                    {item.plaka || tripAnalyticsText.outliers.missingPlate} —{" "}
                    <span className="opacity-50">#{item.id}</span>
                  </div>
                  <div className="mt-1 truncate text-[10px] font-bold uppercase tracking-tight text-tertiary">
                    {item.reason_label}
                  </div>
                </div>
              </div>
              <div className="ml-4 text-right">
                <div className="text-base font-black tracking-tighter text-danger">
                  %{item.sapma_pct.toFixed(1)}
                </div>
                <div className="text-[9px] font-black uppercase tracking-tighter text-tertiary">
                  {tripAnalyticsText.outliers.deviationLabel}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
