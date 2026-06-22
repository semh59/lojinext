import { useQuery } from "@tanstack/react-query";
import { Info, Loader2, AlertCircle } from "lucide-react";
import { driverService } from "../../api/drivers";

interface DriverScoreBreakdownProps {
  driverId: number;
}

function Row({
  label,
  score,
  weight,
  extra,
  accent,
}: {
  label: string;
  score: number;
  weight: number;
  extra?: string;
  accent: string;
}) {
  const contribution = score * weight;
  return (
    <div className="flex items-baseline justify-between gap-4 px-4 py-3 rounded-card bg-elevated/40">
      <div className="min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-widest text-secondary">
          {label}
        </p>
        {extra && <p className="mt-0.5 text-[11px] text-secondary">{extra}</p>}
      </div>
      <div className="flex items-center gap-2 font-mono tabular-nums text-sm">
        <span className={`font-semibold ${accent}`}>{score.toFixed(2)}</span>
        <span className="text-secondary">×</span>
        <span className="text-secondary">{weight.toFixed(2)}</span>
        <span className="text-secondary">=</span>
        <span className="font-bold text-primary">
          {contribution.toFixed(2)}
        </span>
      </div>
    </div>
  );
}

export function DriverScoreBreakdown({ driverId }: DriverScoreBreakdownProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["driverScoreBreakdown", driverId],
    queryFn: () => driverService.getScoreBreakdown(driverId),
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-3 py-12 text-secondary">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span className="text-sm">Skor kırılımı hesaplanıyor…</span>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex items-center justify-center gap-3 py-12 text-danger">
        <AlertCircle className="h-5 w-5" />
        <span className="text-sm">Skor kırılımı alınamadı</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2 rounded-card border border-info/20 bg-info/5 px-4 py-3">
        <Info className="h-4 w-4 shrink-0 text-info mt-0.5" />
        <p className="text-xs leading-relaxed text-secondary">
          Hibrit skor, manuel verilen değerlendirme ile geçmiş seferlerden
          türetilen performans skorunun ağırlıklı toplamıdır. Performans
          bileşeni, araç hedef tüketimi yerine sabit bir filo referansı (
          <span className="font-mono">
            {data.target_reference.toFixed(1)} L/100km
          </span>
          ) üzerinden hesaplanır.
        </p>
      </div>

      <div className="space-y-2">
        <Row
          label="Manuel Puan"
          score={data.manual}
          weight={data.manual_weight}
          extra="yönetici değerlendirmesi"
          accent="text-accent"
        />
        <Row
          label="Otomatik Puan"
          score={data.auto}
          weight={data.auto_weight}
          extra={
            data.has_trips
              ? `${data.trip_count} sefer · ort. ${data.avg_consumption.toFixed(
                  1,
                )} L/100km`
              : "henüz yeterli sefer verisi yok → manuel puana eşit"
          }
          accent={data.has_trips ? "text-success" : "text-warning"}
        />
      </div>

      <div className="flex items-baseline justify-between gap-4 rounded-modal border border-accent/20 bg-accent/5 px-4 py-3">
        <span className="text-[11px] font-bold uppercase tracking-widest text-secondary">
          Toplam Hibrit Skor
        </span>
        <span className="font-mono tabular-nums text-2xl font-black text-accent">
          {data.total.toFixed(2)}
        </span>
      </div>

      {!data.has_trips && (
        <p className="text-[11px] text-secondary text-center">
          Yeterli geçmiş sefer biriktiğinde otomatik puan ayrışacak ve toplam
          değişebilir.
        </p>
      )}
    </div>
  );
}
