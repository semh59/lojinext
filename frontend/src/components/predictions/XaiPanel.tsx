import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui/Card";
import { BrainCircuit, BarChart2 } from "lucide-react";
import { predictionService } from "@/api/predictions";
import { vehicleService } from "@/api/vehicles";

export function EnsembleWeightsPanel() {
  const { t } = useTranslation();
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
            {t("predictions.ensemble_weights_title", "Ensemble Model Weights")}
          </h2>
          <p className="text-xs text-secondary">
            {t(
              "predictions.ensemble_weights_subtitle",
              "Each model's contribution to the prediction",
            )}
          </p>
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-secondary">
          {t("common.loading", "Loading...")}
        </p>
      ) : sortedWeights.length === 0 ? (
        <p className="text-sm text-secondary">
          {t("predictions.ensemble_no_data", "No training data yet")}
        </p>
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
              {t("predictions.ensemble_total_models", "Total models: {{n}}", {
                n: ensemble.total_models,
              })}{" "}
              • LightGBM: {ensemble.lightgbm_available ? "✓" : "✗"} • XGBoost:{" "}
              {ensemble.xgboost_available ? "✓" : "✗"}
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

export function XaiPanel() {
  const { t } = useTranslation();
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
    // Gerçek backend ExplainPredictionResponse şeması bu adları kullanıyor
    // (bkz app/schemas/api_responses.py) — `tahmini_tuketim`/`components`
    // hiçbir zaman dolmuyordu, sonuç her zaman "0.0 L/100km" + boş etki
    // faktörleri gösteriyordu. `prediction`/`contributions` gerçek alanlar.
    prediction?: number | null;
    contributions?: Record<string, number>;
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
  const resultValue = result?.prediction ?? result?.tahmini_tuketim;
  const resultComponents = result?.contributions ?? result?.components;

  const fields = [
    {
      label: t("predictions.distance_total_label", "Distance (km) *"),
      value: mesafe,
      setter: setMesafe,
    },
    {
      label: t("predictions.load_label", "Load (ton)"),
      value: ton,
      setter: setTon,
    },
    {
      label: t("predictions.climb_label", "Climb (m)"),
      value: ascent,
      setter: setAscent,
    },
    {
      label: t("predictions.descent_label", "Descent (m)"),
      value: descent,
      setter: setDescent,
    },
  ];

  return (
    <Card padding="lg" className="flex flex-col gap-6">
      <div className="flex items-center gap-2">
        <BrainCircuit className="h-5 w-5 text-accent" />
        <div>
          <h2 className="text-sm font-semibold text-primary">
            {t("predictions.xai_title", "XAI — Prediction Explanation")}
          </h2>
          <p className="text-xs text-secondary">
            {t(
              "predictions.xai_subtitle",
              "See the factors behind the consumption prediction",
            )}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-secondary">
            {t("predictions.xai_vehicle_label", "Vehicle")}
          </label>
          <select
            className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-primary focus:outline-none focus:ring-2 focus:ring-accent/30"
            value={aracId}
            onChange={(e) => setAracId(Number(e.target.value))}
          >
            <option value={0}>
              {t("predictions.vehicle_placeholder", "Select vehicle")}
            </option>
            {(vehicles?.items ?? []).map((v) => (
              <option key={v.id} value={v.id}>
                {v.plaka}
              </option>
            ))}
          </select>
        </div>
        {fields.map(({ label, value, setter }) => (
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
        {isPending
          ? t("predictions.calculating", "Calculating…")
          : t("predictions.xai_calculate_btn", "Predict + Explain")}
      </button>

      {isError && (
        <p className="text-sm text-danger">
          {t(
            "predictions.xai_error",
            "Prediction could not be calculated. There may not be enough vehicle data.",
          )}
        </p>
      )}

      {result && (
        <div className="rounded-xl border border-border/60 bg-elevated/30 p-4 space-y-3">
          <p className="text-sm font-semibold text-primary">
            {t("predictions.xai_estimated_label", "Estimated Consumption:")}{" "}
            <span className="text-accent">
              {Number(resultValue ?? 0).toFixed(1)} L/100km
            </span>
          </p>
          {resultComponents && Object.keys(resultComponents).length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs font-bold uppercase tracking-wider text-tertiary">
                {t("predictions.xai_impact_factors", "Impact Factors")}
              </p>
              {Object.entries(resultComponents).map(([k, v]) => (
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
