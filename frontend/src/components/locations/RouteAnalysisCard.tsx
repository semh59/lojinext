import { motion } from "framer-motion";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Bot,
  Map,
  Minus,
} from "lucide-react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { routeAnalysisCardText } from "../../resources/tr/locations";
import { RouteAnalysis } from "../../types/location";

interface RouteAnalysisCardProps {
  analysis: RouteAnalysis;
}

export function RouteAnalysisCard({ analysis }: RouteAnalysisCardProps) {
  const highwayFlat = analysis.highway?.flat || 0;
  const highwayUp = analysis.highway?.up || 0;
  const highwayDown = analysis.highway?.down || 0;

  const otherFlat = analysis.other?.flat || 0;
  const otherUp = analysis.other?.up || 0;
  const otherDown = analysis.other?.down || 0;

  const highwayTotal = highwayFlat + highwayUp + highwayDown;
  const otherTotal = otherFlat + otherUp + otherDown;
  const totalDistance = highwayTotal + otherTotal || 1;

  const totalFlat = highwayFlat + otherFlat;
  const totalUp = highwayUp + otherUp;
  const totalDown = highwayDown + otherDown;

  const steepnessData = [
    {
      name: routeAnalysisCardText.steepness.flat,
      value: totalFlat,
      color: "var(--success)",
      icon: Minus,
    },
    {
      name: routeAnalysisCardText.steepness.uphill,
      value: totalUp,
      color: "var(--danger)",
      icon: ArrowUpRight,
    },
    {
      name: routeAnalysisCardText.steepness.downhill,
      value: totalDown,
      color: "var(--warning)",
      icon: ArrowDownRight,
    },
  ].filter((item) => item.value > 0);

  const ratios = analysis.ratios || { otoyol: 0, devlet_yolu: 0, sehir_ici: 0 };
  const roadTypeData = [
    {
      name: routeAnalysisCardText.roadTypes.highway,
      value: ratios.otoyol,
      color: "var(--info)",
      speed: routeAnalysisCardText.roadSpeeds.highway,
    },
    {
      name: routeAnalysisCardText.roadTypes.stateRoad,
      value: ratios.devlet_yolu,
      color: "var(--success)",
      speed: routeAnalysisCardText.roadSpeeds.stateRoad,
    },
    {
      name: routeAnalysisCardText.roadTypes.urban,
      value: ratios.sehir_ici,
      color: "var(--warning)",
      speed: routeAnalysisCardText.roadSpeeds.urban,
    },
  ].filter((item) => item.value > 0);

  const elevationTotal = totalFlat + totalUp + totalDown || 1;

  return (
    <div className="space-y-8 rounded-modal border border-border bg-surface p-6 shadow-sm">
      <div className="flex items-center justify-between border-b border-border pb-6">
        <div className="flex items-center gap-4">
          <div className="rounded-xl bg-accent/10 p-3">
            <Activity className="h-6 w-6 text-accent" />
          </div>
          <div>
            <h3 className="font-bold uppercase tracking-tight text-primary">
              {routeAnalysisCardText.summaryTitle}
            </h3>
            <p className="text-[10px] font-bold uppercase tracking-widest text-secondary">
              {routeAnalysisCardText.summarySubtitle}
            </p>
          </div>
        </div>
        <div className="rounded-full border border-border bg-elevated px-4 py-1.5 text-[10px] font-bold uppercase tracking-widest text-secondary">
          {routeAnalysisCardText.sourceChip}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-12 lg:grid-cols-2">
        <div className="space-y-6">
          <h4 className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-secondary">
            <Map className="h-4 w-4 text-accent" />
            {routeAnalysisCardText.roadDistribution}
          </h4>

          <div className="relative h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={roadTypeData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={8}
                  dataKey="value"
                  stroke="none"
                >
                  {roadTypeData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value?: number | string) => [
                    `%${(Number(value || 0) * 100).toFixed(0)}`,
                    routeAnalysisCardText.tooltipRatio,
                  ]}
                  contentStyle={{
                    borderRadius: "var(--radius-modal)",
                    border: "none",
                    boxShadow: "0 20px 25px -5px rgb(0 0 0 / 0.1)",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>

            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-[10px] font-bold uppercase tracking-tighter text-secondary">
                {routeAnalysisCardText.totalRoute}
              </span>
              <span className="text-2xl font-bold tracking-tighter text-primary">
                {totalDistance.toFixed(0)}
                <span className="ml-1 text-sm font-bold">km</span>
              </span>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2">
            {roadTypeData.map((item) => (
              <div
                key={item.name}
                className="rounded-card border border-border bg-elevated p-3 text-center"
              >
                <div
                  className="mb-1 text-[10px] font-black uppercase tracking-tighter opacity-50"
                  style={{ color: item.color }}
                >
                  {item.name}
                </div>
                <div className="text-xs font-black text-primary">
                  %{Math.round(item.value * 100)}
                </div>
                <div className="mt-1 text-[9px] font-bold uppercase text-secondary">
                  @{item.speed}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          <h4 className="flex items-center gap-2 text-xs font-black uppercase tracking-widest text-secondary">
            <Activity className="h-4 w-4" />
            {routeAnalysisCardText.terrainTitle}
          </h4>

          <div className="mt-4 space-y-5">
            {steepnessData.map((item) => (
              <div key={item.name} className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-3 text-xs font-black uppercase tracking-wider text-primary">
                    <div
                      className="rounded-lg p-2"
                      style={{ backgroundColor: `${item.color}15` }}
                    >
                      <item.icon
                        className="h-4 w-4"
                        style={{ color: item.color }}
                      />
                    </div>
                    {item.name}
                  </span>
                  <div className="text-right">
                    <div className="text-sm font-black tracking-tighter text-primary">
                      {item.value.toFixed(1)} km
                    </div>
                    <div className="text-[10px] font-bold uppercase tracking-widest text-secondary">
                      %{((item.value / elevationTotal) * 100).toFixed(0)}
                    </div>
                  </div>
                </div>
                <div className="h-3 w-full overflow-hidden rounded-full border border-border bg-elevated">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{
                      width: `${(item.value / elevationTotal) * 100}%`,
                    }}
                    className="h-full rounded-full shadow-[inset_0_1px_2px_rgba(0,0,0,0.1)]"
                    style={{ backgroundColor: item.color }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="group relative overflow-hidden rounded-card border border-accent/20 bg-accent/10 p-6 text-primary">
        <div className="relative z-10 space-y-2">
          <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.2em] text-accent">
            <Bot className="h-4 w-4" />
            {routeAnalysisCardText.summaryBoxTitle}
          </div>
          <p className="max-w-2xl text-sm font-medium leading-relaxed text-secondary">
            {routeAnalysisCardText.summaryBoxDescription(ratios.otoyol)}
          </p>
        </div>
      </div>
    </div>
  );
}
