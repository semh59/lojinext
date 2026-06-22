import { Card } from "@/components/ui/Card";
import { routeLabText } from "@/resources/tr/routeLab";
import type { RouteSimResponse } from "@/api/route-sim";

interface Props {
  result: RouteSimResponse;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card padding="md" className="flex flex-col gap-1">
      <span className="text-xs text-secondary">{label}</span>
      <span className="text-lg font-semibold text-primary">{value}</span>
    </Card>
  );
}

export function RouteSimSummary({ result }: Props) {
  const t = routeLabText.summary;
  const s = result.summary;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      <Stat label={t.distance} value={`${s.distance_km.toFixed(1)} ${t.km}`} />
      <Stat
        label={t.duration}
        value={`${s.duration_min.toFixed(0)} ${t.min}`}
      />
      <Stat label={t.totalL} value={`${s.total_l.toFixed(1)} ${t.liters}`} />
      <Stat
        label={t.avg}
        value={`${s.avg_l_per_100km.toFixed(1)} ${t.lper100}`}
      />
      <Stat
        label={t.ascent}
        value={`${s.total_ascent_m.toFixed(0)} ${t.meters}`}
      />
      <Stat
        label={t.descent}
        value={`${s.total_descent_m.toFixed(0)} ${t.meters}`}
      />
      <Stat
        label={t.coverage}
        value={`%${result.elevation_coverage_pct.toFixed(0)}`}
      />
    </div>
  );
}
