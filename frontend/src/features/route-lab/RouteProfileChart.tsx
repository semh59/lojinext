import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card } from "@/components/ui/Card";
import { chartTheme } from "@/lib/chart-theme";
import { routeLabText } from "@/resources/tr/routeLab";
import type { SegmentSim } from "@/api/route-sim";

interface Props {
  segments: SegmentSim[];
}

/** Segment dizisi → kümülatif mesafe profili (chart için saf dönüşüm). */
export function buildProfile(segments: SegmentSim[]) {
  let cum = 0;
  return segments.map((s) => {
    cum += s.length_km;
    return {
      km: Number(cum.toFixed(1)),
      speed: Number(s.sim_speed_kmh.toFixed(1)),
      consumption: Number(s.sim_l_per_100km.toFixed(1)),
      grade: Number(s.grade_pct.toFixed(1)),
    };
  });
}

export function RouteProfileChart({ segments }: Props) {
  const data = useMemo(() => buildProfile(segments), [segments]);

  return (
    <Card padding="lg" className="flex flex-col gap-3">
      <div>
        <h2 className="text-sm font-semibold text-primary">
          {routeLabText.profile.title}
        </h2>
        <p className="text-xs text-secondary">
          {routeLabText.profile.subtitle}
        </p>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={data}>
          <CartesianGrid {...chartTheme.grid} />
          <XAxis
            dataKey="km"
            tick={chartTheme.tickSmall}
            axisLine={false}
            tickLine={false}
            unit=" km"
          />
          <YAxis
            yAxisId="left"
            tick={chartTheme.tickSmall}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={chartTheme.tickSmall}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip />
          <Area
            yAxisId="right"
            type="monotone"
            dataKey="grade"
            name={routeLabText.profile.grade}
            fill="#94a3b8"
            stroke="#94a3b8"
            fillOpacity={0.2}
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="speed"
            name={routeLabText.profile.speed}
            stroke="#3b82f6"
            dot={false}
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="consumption"
            name={routeLabText.profile.consumption}
            stroke="#ef4444"
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </Card>
  );
}
