import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CalendarRange,
  Loader2,
  AlertCircle,
  MapPin,
  Fuel,
  Receipt,
  Route as RouteIcon,
  Wallet,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { reportService } from "@/api/reports";
import { useLocale } from "../../hooks/useLocale";

interface PeriodCostBreakdownProps {
  /** Drill-down için tek araca sabitlemek. */
  aracId?: number;
  /** Drill-down başlığında plakayı göstermek için. */
  plakaLabel?: string;
}

function todayIso(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

const TRY = (v: number, locale: string) =>
  new Intl.NumberFormat(locale, {
    style: "currency",
    currency: "TRY",
    maximumFractionDigits: 0,
  }).format(v);

export function PeriodCostBreakdown({
  aracId,
  plakaLabel,
}: PeriodCostBreakdownProps) {
  const locale = useLocale();
  const [startDate, setStartDate] = useState(todayIso(-30));
  const [endDate, setEndDate] = useState(todayIso());

  const { data, isLoading, isError } = useQuery({
    queryKey: ["period-cost", startDate, endDate, aracId ?? null],
    queryFn: () => reportService.getPeriodCost(startDate, endDate, aracId),
    staleTime: 5 * 60 * 1000,
    enabled: Boolean(startDate && endDate && startDate <= endDate),
  });

  return (
    <Card padding="lg" className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <CalendarRange className="h-5 w-5 text-accent" />
          <div>
            <h2 className="text-sm font-semibold text-primary">
              Dönem Maliyet Detayı
              {plakaLabel && (
                <span className="ml-2 rounded-card bg-elevated px-2 py-0.5 font-mono text-[11px] text-secondary">
                  {plakaLabel}
                </span>
              )}
            </h2>
            <p className="text-xs text-secondary">
              Seçili tarih aralığında {aracId ? "aracın" : "filonun"}{" "}
              yakıt/maliyet özeti.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="input-base !w-40"
            aria-label="Başlangıç tarihi"
          />
          <span className="text-secondary">→</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="input-base !w-40"
            aria-label="Bitiş tarihi"
          />
        </div>
      </div>

      {startDate > endDate && (
        <div className="flex items-center gap-2 rounded-card border border-warning/30 bg-warning/5 px-4 py-2 text-xs text-warning">
          <AlertCircle className="h-4 w-4" />
          Başlangıç tarihi bitiş tarihinden büyük olamaz.
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center gap-2 py-6 text-secondary text-sm">
          <Loader2 className="h-4 w-4 animate-spin" /> Hesaplanıyor…
        </div>
      ) : isError ? (
        <div className="flex items-center gap-2 rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          <AlertCircle className="h-4 w-4" /> Dönem maliyeti alınamadı.
        </div>
      ) : data ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
          <Tile
            icon={Receipt}
            label="Yakıt Maliyeti"
            value={TRY(Number(data.fuel_cost ?? 0), locale)}
            accent="text-warning"
            bg="bg-warning/10"
          />
          <Tile
            icon={Wallet}
            label="₺ / km"
            value={`${Number(data.cost_per_km ?? 0).toFixed(2)} ₺`}
            accent="text-accent"
            bg="bg-accent/10"
          />
          <Tile
            icon={Fuel}
            label="₺ / Litre"
            value={`${Number(data.avg_price_per_liter ?? 0).toFixed(2)} ₺`}
            accent="text-info"
            bg="bg-info/10"
          />
          <Tile
            icon={RouteIcon}
            label="Toplam Sefer"
            value={Number(data.trip_count ?? 0).toLocaleString(locale)}
            accent="text-secondary"
            bg="bg-elevated"
          />
          <Tile
            icon={MapPin}
            label="Toplam km"
            value={`${Number(data.total_distance ?? 0).toLocaleString(locale, {
              maximumFractionDigits: 0,
            })} km`}
            accent="text-success"
            bg="bg-success/10"
          />
        </div>
      ) : null}
    </Card>
  );
}

function Tile({
  icon: Icon,
  label,
  value,
  accent,
  bg,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  accent: string;
  bg: string;
}) {
  return (
    <div className="rounded-modal border border-border bg-surface p-4">
      <div
        className={`mb-2 inline-flex h-8 w-8 items-center justify-center rounded-card ${bg}`}
      >
        <Icon className={`h-4 w-4 ${accent}`} />
      </div>
      <p className="text-[10px] font-bold uppercase tracking-widest text-secondary">
        {label}
      </p>
      <p className={`mt-1 text-lg font-bold ${accent}`}>{value}</p>
    </div>
  );
}
