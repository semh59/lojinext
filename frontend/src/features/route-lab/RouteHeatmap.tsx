import { useMemo, useState } from "react";

import { Card } from "@/components/ui/Card";
import type { SegmentSim } from "@/api/route-sim";
import { useRouteLabResources } from "@/resources/useResources";

const W = 600;
const H = 360;
const PAD = 16;

/** L/100km → renk eşiği (yeşil < 30 ≤ kehribar < 40 ≤ kırmızı). Saf fonksiyon. */
export function colorForConsumption(lPer100: number): string {
  if (lPer100 < 30) return "#22c55e";
  if (lPer100 < 40) return "#f59e0b";
  return "#ef4444";
}

/** lon/lat → SVG viewBox koordinatı (equirectangular, lat ters). Saf fonksiyon. */
export function projectPoint(
  lon: number,
  lat: number,
  bounds: { minLon: number; maxLon: number; minLat: number; maxLat: number },
): { x: number; y: number } {
  const spanLon = bounds.maxLon - bounds.minLon || 1e-9;
  const spanLat = bounds.maxLat - bounds.minLat || 1e-9;
  const x = PAD + ((lon - bounds.minLon) / spanLon) * (W - 2 * PAD);
  const y = PAD + ((bounds.maxLat - lat) / spanLat) * (H - 2 * PAD);
  return { x, y };
}

interface Props {
  segments: SegmentSim[];
}

export function RouteHeatmap({ segments }: Props) {
  const { routeLabText } = useRouteLabResources();
  const pts = useMemo(
    () =>
      segments.filter(
        (s): s is SegmentSim & { mid_lon: number; mid_lat: number } =>
          s.mid_lon != null && s.mid_lat != null,
      ),
    [segments],
  );
  const [hover, setHover] = useState<number | null>(null);

  const bounds = useMemo(() => {
    if (pts.length === 0) return { minLon: 0, maxLon: 1, minLat: 0, maxLat: 1 };
    const lons = pts.map((s) => s.mid_lon);
    const lats = pts.map((s) => s.mid_lat);
    return {
      minLon: Math.min(...lons),
      maxLon: Math.max(...lons),
      minLat: Math.min(...lats),
      maxLat: Math.max(...lats),
    };
  }, [pts]);

  return (
    <Card padding="lg" className="flex flex-col gap-3">
      <div>
        <h2 className="text-sm font-semibold text-primary">
          {routeLabText.heatmap.title}
        </h2>
        <p className="text-xs text-secondary">
          {routeLabText.heatmap.subtitle}
        </p>
      </div>
      {pts.length === 0 ? (
        <div className="flex h-48 items-center justify-center text-sm text-secondary">
          {routeLabText.heatmap.noCoords}
        </div>
      ) : (
        <>
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="w-full rounded-card bg-elevated/40"
            role="img"
            aria-label={routeLabText.heatmap.title}
          >
            {pts.slice(0, -1).map((s, i) => {
              const a = projectPoint(s.mid_lon, s.mid_lat, bounds);
              const next = pts[i + 1];
              const b = projectPoint(next.mid_lon, next.mid_lat, bounds);
              return (
                <line
                  key={s.seq}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={colorForConsumption(s.sim_l_per_100km)}
                  strokeWidth={hover === s.seq ? 7 : 4}
                  strokeLinecap="round"
                  onMouseEnter={() => setHover(s.seq)}
                  onMouseLeave={() => setHover(null)}
                />
              );
            })}
          </svg>
          {hover != null &&
            (() => {
              const s = pts.find((p) => p.seq === hover);
              if (!s) return null;
              return (
                <div className="text-xs text-secondary">
                  #{s.seq} · {s.road_class || "—"} ·{" "}
                  {s.sim_speed_kmh.toFixed(0)} km/h ·{" "}
                  {s.sim_l_per_100km.toFixed(1)} L/100km · %
                  {s.grade_pct.toFixed(1)}
                </div>
              );
            })()}
          <div className="flex gap-4 text-xs text-secondary">
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-3 rounded-sm bg-[#22c55e]" />
              {routeLabText.heatmap.legendLow}
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-3 rounded-sm bg-[#f59e0b]" />
              {routeLabText.heatmap.legendMid}
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-3 rounded-sm bg-[#ef4444]" />
              {routeLabText.heatmap.legendHigh}
            </span>
          </div>
        </>
      )}
    </Card>
  );
}
