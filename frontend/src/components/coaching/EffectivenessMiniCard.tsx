import { useQuery } from "@tanstack/react-query";
import { Info, Send, Sparkles, TrendingDown, TrendingUp } from "lucide-react";
import { Card } from "../ui/Card";
import { coachingService } from "../../api/coaching";

export function EffectivenessMiniCard({ days = 30 }: { days?: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["coaching", "effectiveness", days],
    queryFn: () => coachingService.getEffectiveness(days),
    staleTime: 60 * 60 * 1000,
  });

  return (
    <Card padding="md" className="space-y-2">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h3 className="text-xs font-bold uppercase tracking-widest text-secondary">
          Son {days} Gün Etkinliği
        </h3>
        {isLoading && (
          <span className="text-[10px] text-tertiary">yükleniyor…</span>
        )}
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Stat
          icon={Send}
          label="Gönderilen"
          value={data?.total_sent ?? 0}
          accent="text-info"
          bg="bg-info/10"
        />
        <Stat
          icon={Sparkles}
          label="İyileşme"
          value={
            data?.improve_rate != null
              ? `%${Math.round(data.improve_rate * 100)}`
              : "—"
          }
          sub={
            data && data.total_evaluated > 0
              ? `${data.improved}/${data.total_evaluated} değerlendirildi`
              : "Henüz değerlendirme yok"
          }
          accent="text-success"
          bg="bg-success/10"
        />
        <Stat
          icon={
            data && (data.avg_score_delta_pct ?? 0) > 0
              ? TrendingUp
              : TrendingDown
          }
          label="Ortalama Δ"
          value={
            data?.avg_score_delta_pct != null
              ? `${
                  data.avg_score_delta_pct > 0 ? "+" : ""
                }${data.avg_score_delta_pct.toFixed(1)}%`
              : "—"
          }
          accent={
            data && (data.avg_score_delta_pct ?? 0) >= 0
              ? "text-success"
              : "text-warning"
          }
          bg={
            data && (data.avg_score_delta_pct ?? 0) >= 0
              ? "bg-success/10"
              : "bg-warning/10"
          }
        />
      </div>

      {data && (
        <p className="flex items-start gap-1.5 text-[10px] italic text-tertiary leading-snug">
          <Info className="h-3 w-3 shrink-0 mt-0.5" />
          {data.caveat}
        </p>
      )}
    </Card>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
  sub,
  accent,
  bg,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  sub?: string;
  accent: string;
  bg: string;
}) {
  return (
    <div className={`rounded-card border border-border p-2.5 ${bg}`}>
      <div className="flex items-center gap-1.5">
        <Icon className={`h-3 w-3 ${accent}`} />
        <p className="text-[9px] font-bold uppercase tracking-widest text-secondary">
          {label}
        </p>
      </div>
      <p className={`mt-1 text-lg font-bold ${accent} tabular-nums`}>{value}</p>
      {sub && <p className="text-[9px] text-tertiary mt-0.5">{sub}</p>}
    </div>
  );
}
