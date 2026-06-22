import { motion } from "framer-motion";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { reportChartText } from "../../resources/tr/reports";
import type { MonthlyCostTrend } from "../../api/reports";

interface CostAnalysisChartProps {
  data: MonthlyCostTrend[];
}

export function CostAnalysisChart({ data }: CostAnalysisChartProps) {
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="min-w-[160px] rounded-2xl border border-border bg-surface/90 p-4 shadow-2xl backdrop-blur-md">
          <p className="mb-3 border-b border-border pb-2 text-[10px] font-black uppercase tracking-widest text-tertiary">
            {label}
          </p>
          <div className="space-y-2">
            {payload.map((entry: any, index: number) => (
              <div
                key={index}
                className="flex items-center justify-between gap-4"
              >
                <div className="flex items-center gap-2">
                  <div
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ backgroundColor: entry.color }}
                  />
                  <span className="text-xs font-bold uppercase tracking-tight text-secondary">
                    {entry.name === "fuel"
                      ? reportChartText.fuel
                      : reportChartText.maintenance}
                  </span>
                </div>
                <span className="tabular-nums text-sm font-black text-primary">
                  {entry.value.toLocaleString()} ₺
                </span>
              </div>
            ))}
            <div className="mt-1 flex items-center justify-between gap-4 border-t border-border pt-2">
              <span className="text-[10px] font-black uppercase tracking-tighter text-primary">
                {reportChartText.total}
              </span>
              <span className="tabular-nums text-sm font-black text-accent">
                {(
                  Number(payload[0]?.value || 0) +
                  Number(payload[1]?.value || 0)
                ).toLocaleString()}{" "}
                ₺
              </span>
            </div>
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex h-[450px] w-full flex-col bg-transparent"
    >
      <div className="mb-10 flex flex-col justify-between gap-4 px-2 md:flex-row md:items-center">
        <div>
          <h3 className="text-lg font-bold text-primary">
            {reportChartText.title}
          </h3>
          <p className="mt-1 text-xs font-medium italic text-secondary opacity-70">
            {reportChartText.subtitle}
          </p>
        </div>
        <div className="flex gap-6">
          <div className="flex items-center gap-2.5">
            <div className="h-2.5 w-2.5 rounded-full bg-accent shadow-[0_0_8px_rgba(232,93,47,0.4)]" />
            <span className="text-[10px] font-black uppercase tracking-[0.15em] text-secondary">
              {reportChartText.fuel}
            </span>
          </div>
          <div className="flex items-center gap-2.5">
            <div className="h-2.5 w-2.5 rounded-full bg-warning shadow-[0_0_8px_rgba(180,83,9,0.4)]" />
            <span className="text-[10px] font-black uppercase tracking-[0.15em] text-secondary">
              {reportChartText.maintenance}
            </span>
          </div>
        </div>
      </div>

      <div className="group relative flex-1 rounded-[32px] border border-border/40 bg-elevated p-6">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            barGap={8}
            margin={{ top: 20, right: 30, left: 0, bottom: 0 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              vertical={false}
              stroke="var(--border)"
              opacity={0.4}
            />
            <XAxis
              dataKey="label"
              axisLine={false}
              tickLine={false}
              tick={{
                fill: "var(--text-tertiary)",
                fontSize: 10,
                fontWeight: 800,
              }}
              dy={15}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{
                fill: "var(--text-tertiary)",
                fontSize: 10,
                fontWeight: 800,
              }}
              tickFormatter={(value) => `${value / 1000}k`}
              dx={-10}
            />
            <Tooltip
              content={<CustomTooltip />}
              cursor={{ fill: "rgba(232, 93, 47, 0.03)" }}
              animationDuration={200}
            />
            <Bar
              name="fuel"
              dataKey="fuel"
              stackId="a"
              fill="var(--accent)"
              radius={[0, 0, 8, 8]}
              className="transition-all duration-300 hover:opacity-80"
            >
              {data.map((_, index) => (
                <Cell key={`cell-fuel-${index}`} fill="var(--accent)" />
              ))}
            </Bar>
            <Bar
              name="maintenance"
              dataKey="maintenance"
              stackId="a"
              fill="var(--warning)"
              radius={[8, 8, 0, 0]}
              className="transition-all duration-300 hover:opacity-80"
            >
              {data.map((_, index) => (
                <Cell key={`cell-maint-${index}`} fill="var(--warning)" />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        <div className="absolute -bottom-1 -right-1 -z-10 h-24 w-24 rounded-full bg-accent/5 blur-3xl transition-all duration-700 group-hover:bg-accent/10" />
      </div>
    </motion.div>
  );
}
