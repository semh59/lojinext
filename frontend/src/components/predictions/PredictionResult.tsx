import { Droplet, TrendingUp, Wallet } from "lucide-react";
import { Card } from "@/components/ui/Card";
import type { PredictionResult as PredictionResultModel } from "@/types";

interface PredictionResultProps {
  result: PredictionResultModel;
  mesafeKm: number;
  /** TL/Litre referans fiyatı (UI-only; uygulama bazlı sabit). */
  unitPriceTL?: number;
}

const DEFAULT_UNIT_PRICE = 42.5;

export function PredictionResult({
  result,
  mesafeKm,
  unitPriceTL = DEFAULT_UNIT_PRICE,
}: PredictionResultProps) {
  const tuketim = Number(result.tahmini_tuketim ?? 0); // L/100km
  const totalLiters = result.tahmini_litre ?? (tuketim * mesafeKm) / 100;
  const projectedCost = totalLiters * unitPriceTL;

  // Güven değeri zorunlu değil; varsa min/max'tan türetilir.
  const confidence = (() => {
    if (result.confidence_low != null && result.confidence_high != null) {
      const range = Math.abs(result.confidence_high - result.confidence_low);
      const ratio = tuketim > 0 ? 1 - Math.min(1, range / (tuketim * 2)) : 0;
      return Math.round(ratio * 100);
    }
    return null;
  })();

  return (
    <Card padding="lg" className="space-y-4">
      <h3 className="text-sm font-semibold text-primary">Tahmin Sonucu</h3>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Tile
          icon={Droplet}
          label="Tahmini Tüketim"
          value={`${tuketim.toFixed(1)} L/100km`}
          sub={`Toplam ≈ ${totalLiters.toLocaleString("tr-TR", {
            maximumFractionDigits: 1,
          })} L`}
          accent="text-info"
          bg="bg-info/10"
        />
        <Tile
          icon={Wallet}
          label="Maliyet Projeksiyonu"
          value={projectedCost.toLocaleString("tr-TR", {
            style: "currency",
            currency: "TRY",
            maximumFractionDigits: 0,
          })}
          sub={`${unitPriceTL.toFixed(2)} ₺/L referansı`}
          accent="text-warning"
          bg="bg-warning/10"
        />
        <Tile
          icon={TrendingUp}
          label="Güven Skoru"
          value={confidence != null ? `%${confidence}` : "—"}
          sub={
            result.confidence_low != null && result.confidence_high != null
              ? `${result.confidence_low.toFixed(
                  1,
                )} – ${result.confidence_high.toFixed(1)} L/100km`
              : "güven aralığı dönmedi"
          }
          accent="text-success"
          bg="bg-success/10"
        />
      </div>

      {result.insight && (
        <p className="rounded-card border border-border bg-elevated/30 px-4 py-3 text-xs text-secondary">
          {result.insight}
        </p>
      )}

      <p className="text-[10px] uppercase tracking-widest text-tertiary">
        Model: {result.model_used ?? "—"}
      </p>
    </Card>
  );
}

function Tile({
  icon: Icon,
  label,
  value,
  sub,
  accent,
  bg,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  sub?: string;
  accent: string;
  bg: string;
}) {
  return (
    <div className="rounded-modal border border-border bg-surface p-5">
      <div
        className={`mb-3 inline-flex h-9 w-9 items-center justify-center rounded-xl ${bg}`}
      >
        <Icon className={`h-4 w-4 ${accent}`} />
      </div>
      <p className="text-[10px] font-bold uppercase tracking-widest text-secondary">
        {label}
      </p>
      <p className={`mt-1 text-2xl font-bold ${accent}`}>{value}</p>
      {sub && <p className="mt-1 text-[11px] text-secondary">{sub}</p>}
    </div>
  );
}
