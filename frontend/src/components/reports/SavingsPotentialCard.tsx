import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { TrendingDown, Sparkles, AlertCircle, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { reportService } from "@/api/reports";

interface SavingsResult {
  current_consumption?: number;
  target_consumption?: number;
  current_cost?: number;
  target_cost?: number;
  potential_savings?: number;
  savings_percentage?: number;
  annual_projection?: number;
  // legacy
  current_avg?: number;
  target_avg?: number;
  potential_savings_liters?: number;
  potential_savings_tl?: number;
}

function pickMonthly(d: SavingsResult): number {
  return Number(d.potential_savings ?? d.potential_savings_tl ?? 0);
}

function pickPercentage(d: SavingsResult): number {
  return Number(d.savings_percentage ?? 0);
}

function pickAnnual(d: SavingsResult): number {
  return Number(d.annual_projection ?? pickMonthly(d) * 12);
}

const TRY = (v: number) =>
  new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: "TRY",
    maximumFractionDigits: 0,
  }).format(v);

export function SavingsPotentialCard() {
  const [target, setTarget] = useState(30);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["savings-potential", target],
    queryFn: () => reportService.getSavingsPotential(target),
    staleTime: 5 * 60 * 1000,
  });

  const savings = data as SavingsResult | undefined;
  const monthly = savings ? pickMonthly(savings) : 0;
  const annual = savings ? pickAnnual(savings) : 0;
  const pct = savings ? pickPercentage(savings) : 0;
  const currentAvg = savings?.current_consumption ?? savings?.current_avg;

  // Backend yeterli veri olmadığında 409 dönüyor → axios throw eder.
  const isConflict = isError && (error as any)?.response?.status === 409;

  return (
    <Card padding="lg" className="space-y-5">
      <div className="flex items-center gap-2">
        <Sparkles className="h-5 w-5 text-success" />
        <div>
          <h2 className="text-sm font-semibold text-primary">
            Tasarruf Potansiyeli
          </h2>
          <p className="text-xs text-secondary">
            Hedef tüketime indirildiğinde elde edilecek aylık/yıllık kazanım.
          </p>
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <label className="text-[11px] font-bold uppercase tracking-widest text-secondary">
            Hedef Tüketim
          </label>
          <span className="font-mono tabular-nums text-sm font-semibold text-primary">
            {target.toFixed(1)} L/100km
          </span>
        </div>
        <input
          type="range"
          min={20}
          max={45}
          step={0.5}
          value={target}
          onChange={(e) => setTarget(Number(e.target.value))}
          className="h-2 w-full cursor-pointer accent-success"
          aria-label="Hedef tüketim"
        />
        <div className="mt-1 flex justify-between text-[10px] text-tertiary font-mono">
          <span>20</span>
          <span>30</span>
          <span>45</span>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 py-4 text-secondary text-sm">
          <Loader2 className="h-4 w-4 animate-spin" /> Hesaplanıyor…
        </div>
      ) : isConflict ? (
        <div className="flex items-center gap-2 rounded-card border border-warning/30 bg-warning/5 px-4 py-3 text-xs text-secondary">
          <AlertCircle className="h-4 w-4 text-warning" />
          Gerçek maliyet verisi henüz yeterli değil — tasarruf hesabı pas
          geçildi.
        </div>
      ) : isError ? (
        <div className="flex items-center gap-2 rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          <AlertCircle className="h-4 w-4" /> Tasarruf potansiyeli
          hesaplanamadı.
        </div>
      ) : data ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Stat
            label="Aylık Potansiyel"
            value={TRY(monthly)}
            accent="text-success"
            bg="bg-success/10"
          />
          <Stat
            label="Yıllık Projeksiyon"
            value={TRY(annual)}
            accent="text-accent"
            bg="bg-accent/10"
          />
          <Stat
            label="İyileşme %"
            value={`${pct.toFixed(1)}%`}
            accent={pct > 0 ? "text-success" : "text-tertiary"}
            bg={pct > 0 ? "bg-success/10" : "bg-elevated"}
          />
        </div>
      ) : null}

      {currentAvg != null && (
        <p className="flex items-center gap-2 text-[11px] text-secondary">
          <TrendingDown className="h-3 w-3 text-success" />
          Mevcut ortalama:{" "}
          <span className="font-mono">
            {Number(currentAvg).toFixed(1)} L/100km
          </span>
        </p>
      )}
    </Card>
  );
}

function Stat({
  label,
  value,
  accent,
  bg,
}: {
  label: string;
  value: string;
  accent: string;
  bg: string;
}) {
  return (
    <div className={`rounded-card border border-border p-3 ${bg}`}>
      <p className="text-[10px] font-bold uppercase tracking-widest text-secondary">
        {label}
      </p>
      <p className={`mt-1 text-xl font-bold ${accent}`}>{value}</p>
    </div>
  );
}
