import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/Card";
import { BrainCircuit, BarChart2 } from "lucide-react";
import { predictionService } from "@/api/predictions";
import { vehicleService } from "@/api/vehicles";

export function EnsembleWeightsPanel() {
  const { data: ensemble, isLoading } = useQuery({
    queryKey: ["predictions-ensemble"],
    queryFn: () => predictionService.getEnsembleStatus(),
    staleTime: 5 * 60 * 1000,
  });

  const weights = ensemble?.weights ?? {};
  const sortedWeights = Object.entries(weights).sort(([, a], [, b]) => b - a);

  return (
    <Card padding="lg" className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <BarChart2 className="h-5 w-5 text-accent" />
        <div>
          <h2 className="text-sm font-semibold text-primary">
            Ensemble Model Ağırlıkları
          </h2>
          <p className="text-xs text-secondary">
            Her modelin tahmine katkı oranı
          </p>
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-secondary">Yükleniyor...</p>
      ) : sortedWeights.length === 0 ? (
        <p className="text-sm text-secondary">Henüz eğitim verisi yok.</p>
      ) : (
        <div className="space-y-3">
          {sortedWeights.map(([model, weight]) => (
            <div key={model} className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-secondary capitalize">{model}</span>
                <span className="font-medium text-primary">
                  {(weight * 100).toFixed(1)}%
                </span>
              </div>
              <div className="h-2 rounded-full bg-surface overflow-hidden">
                <div
                  className="h-full rounded-full bg-accent transition-all duration-500"
                  style={{ width: `${weight * 100}%` }}
                />
              </div>
            </div>
          ))}
          {ensemble && (
            <p className="pt-1 text-xs text-secondary">
              Toplam model: {ensemble.total_models} • LightGBM:{" "}
              {ensemble.lightgbm_available ? "✓" : "✗"} • XGBoost:{" "}
              {ensemble.xgboost_available ? "✓" : "✗"}
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

export function XaiPanel() {
  const [aracId, setAracId] = useState(0);
  const [mesafe, setMesafe] = useState(100);
  const [ton, setTon] = useState(0);
  const [ascent, setAscent] = useState(0);
  const [descent, setDescent] = useState(0);

  const { data: vehicles } = useQuery({
    queryKey: ["xai-vehicles"],
    queryFn: () => vehicleService.getAll({ aktif_only: true, limit: 100 }),
    staleTime: 10 * 60 * 1000,
  });

  interface ExplainResult {
    tahmini_tuketim?: number | null;
    components?: Record<string, number>;
    [key: string]: unknown;
  }

  const {
    mutate,
    data: rawResult,
    isPending,
    isError,
  } = useMutation({
    mutationFn: () =>
      predictionService.explain({
        arac_id: aracId,
        mesafe_km: mesafe,
        ton,
        ascent_m: ascent,
        descent_m: descent,
        flat_distance_km: mesafe,
      }),
  });
  const result = rawResult as ExplainResult | undefined;

  return (
    <Card padding="lg" className="flex flex-col gap-6">
      <div className="flex items-center gap-2">
        <BrainCircuit className="h-5 w-5 text-accent" />
        <div>
          <h2 className="text-sm font-semibold text-primary">
            XAI — Tahmin Açıklama
          </h2>
          <p className="text-xs text-secondary">
            Tüketim tahmininin faktörlerini görün
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-secondary">
            Araç
          </label>
          <select
            className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-primary focus:outline-none focus:ring-2 focus:ring-accent/30"
            value={aracId}
            onChange={(e) => setAracId(Number(e.target.value))}
          >
            <option value={0}>Araç seçin</option>
            {(vehicles?.items ?? []).map((v) => (
              <option key={v.id} value={v.id}>
                {v.plaka}
              </option>
            ))}
          </select>
        </div>
        {[
          { label: "Mesafe (km)", value: mesafe, setter: setMesafe },
          { label: "Yük (ton)", value: ton, setter: setTon },
          { label: "Tırmanış (m)", value: ascent, setter: setAscent },
          { label: "İniş (m)", value: descent, setter: setDescent },
        ].map(({ label, value, setter }) => (
          <div key={label}>
            <label className="mb-1 block text-xs font-medium text-secondary">
              {label}
            </label>
            <input
              type="number"
              min={0}
              value={value}
              onChange={(e) => setter(Number(e.target.value))}
              className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-primary focus:outline-none focus:ring-2 focus:ring-accent/30"
            />
          </div>
        ))}
      </div>

      <button
        onClick={() => mutate()}
        disabled={isPending || aracId === 0}
        className="w-fit rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-50 transition-colors"
      >
        {isPending ? "Hesaplanıyor..." : "Tahmin Et + Açıkla"}
      </button>

      {isError && (
        <p className="text-sm text-danger">
          Tahmin hesaplanamadı. Araç verisi yeterli olmayabilir.
        </p>
      )}

      {result && (
        <div className="rounded-xl border border-border/60 bg-elevated/30 p-4 space-y-3">
          <p className="text-sm font-semibold text-primary">
            Tahmini Tüketim:{" "}
            <span className="text-accent">
              {Number(result.tahmini_tuketim ?? 0).toFixed(1)} L/100km
            </span>
          </p>
          {result.components &&
            Object.keys(result.components as Record<string, number>).length >
              0 && (
              <div className="space-y-1.5">
                <p className="text-xs font-bold uppercase tracking-wider text-tertiary">
                  Etki Faktörleri
                </p>
                {Object.entries(
                  result.components as Record<string, number>,
                ).map(([k, v]) => (
                  <div
                    key={k}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="text-secondary">{k}</span>
                    <span className="font-medium text-primary">
                      {(v * 100).toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            )}
        </div>
      )}
    </Card>
  );
}
