import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui/Card";
import { BrainCircuit, Loader2, AlertCircle } from "lucide-react";
import { predictionService } from "@/api/predictions";
import { vehicleService } from "@/api/vehicles";
import { driverService } from "@/api/drivers";
import { PredictionResult } from "./PredictionResult";
import { XaiExplainPanel } from "./XaiExplainPanel";

type Difficulty = "Normal" | "Orta" | "Zor";

interface SimulatorState {
  aracId: number;
  mesafe: number;
  ton: number;
  ascent: number;
  descent: number;
  flatDistance: number;
  soforId: number | null;
  zorluk: Difficulty;
}

const INITIAL: SimulatorState = {
  aracId: 0,
  mesafe: 100,
  ton: 22,
  ascent: 0,
  descent: 0,
  flatDistance: 100,
  soforId: null,
  zorluk: "Normal",
};

export function PredictionSimulator() {
  const { t } = useTranslation();
  const [form, setForm] = useState<SimulatorState>(INITIAL);
  const [showExplain, setShowExplain] = useState(false);

  const { data: vehiclesData } = useQuery({
    queryKey: ["simulator-vehicles"],
    queryFn: () => vehicleService.getAll({ aktif_only: true, limit: 200 }),
    staleTime: 10 * 60 * 1000,
  });
  const vehicles = (vehiclesData?.items ?? []) as Array<{
    id: number;
    plaka: string;
  }>;

  const { data: driversData } = useQuery({
    queryKey: ["simulator-drivers"],
    queryFn: () => driverService.getAll({ aktif_only: true, limit: 200 }),
    staleTime: 10 * 60 * 1000,
  });
  const drivers = (driversData?.items ?? []) as Array<{
    id: number;
    ad_soyad: string;
  }>;

  const requestPayload = useMemo(
    () => ({
      arac_id: form.aracId,
      mesafe_km: form.mesafe,
      ton: form.ton,
      ascent_m: form.ascent,
      descent_m: form.descent,
      flat_distance_km: form.flatDistance,
      zorluk: form.zorluk,
      ...(form.soforId !== null && form.soforId > 0
        ? { sofor_id: form.soforId }
        : {}),
    }),
    [form],
  );

  const predict = useMutation({
    mutationFn: () => predictionService.predict(requestPayload),
    onSuccess: () => setShowExplain(false),
  });

  const canSubmit = form.aracId > 0 && form.mesafe > 0 && !predict.isPending;

  return (
    <div className="space-y-6">
      <Card padding="lg" className="flex flex-col gap-5">
        <div className="flex items-center gap-2">
          <BrainCircuit className="h-5 w-5 text-accent" />
          <div>
            <h2 className="text-sm font-semibold text-primary">
              {t("predictions.simulator_title", "Trip Simulation")}
            </h2>
            <p className="text-xs text-secondary">
              {t(
                "predictions.simulator_subtitle",
                "Calculate estimated fuel consumption and cost projection for a hypothetical trip.",
              )}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Field label={t("predictions.vehicle_label", "Vehicle *")}>
            <select
              className="input-base"
              value={form.aracId}
              onChange={(e) =>
                setForm({ ...form, aracId: Number(e.target.value) })
              }
            >
              <option value={0}>
                {t("predictions.vehicle_placeholder", "Select vehicle")}
              </option>
              {vehicles.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.plaka}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("predictions.driver_label", "Driver")}>
            <select
              className="input-base"
              value={form.soforId ?? 0}
              onChange={(e) =>
                setForm({ ...form, soforId: Number(e.target.value) || null })
              }
            >
              <option value={0}>
                {t("predictions.driver_optional", "(optional)")}
              </option>
              {drivers.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.ad_soyad}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("predictions.difficulty_label", "Difficulty")}>
            <select
              className="input-base"
              value={form.zorluk}
              onChange={(e) =>
                setForm({ ...form, zorluk: e.target.value as Difficulty })
              }
            >
              <option value="Normal">
                {t("predictions.difficulty_normal", "Normal")}
              </option>
              <option value="Orta">
                {t("predictions.difficulty_medium", "Medium")}
              </option>
              <option value="Zor">
                {t("predictions.difficulty_hard", "Hard")}
              </option>
            </select>
          </Field>
          <NumberField
            label={t("predictions.distance_total_label", "Distance (km) *")}
            value={form.mesafe}
            onChange={(v) =>
              setForm({
                ...form,
                mesafe: v,
                flatDistance: Math.max(
                  0,
                  v - (form.ascent + form.descent) / 100,
                ),
              })
            }
          />
          <NumberField
            label={t("predictions.load_label", "Load (ton)")}
            value={form.ton}
            onChange={(v) => setForm({ ...form, ton: v })}
          />
          <NumberField
            label={t("predictions.climb_label", "Climb (m)")}
            value={form.ascent}
            onChange={(v) => setForm({ ...form, ascent: v })}
          />
          <NumberField
            label={t("predictions.descent_label", "Descent (m)")}
            value={form.descent}
            onChange={(v) => setForm({ ...form, descent: v })}
          />
          <NumberField
            label={t("predictions.distance_label", "Flat Distance (km)")}
            value={form.flatDistance}
            onChange={(v) => setForm({ ...form, flatDistance: v })}
          />
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => predict.mutate()}
            disabled={!canSubmit}
            className="rounded-card bg-accent px-5 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {predict.isPending ? (
              <span className="inline-flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                {t("predictions.calculating", "Calculating…")}
              </span>
            ) : (
              t("predictions.calculate_btn", "Calculate Estimate")
            )}
          </button>
          {predict.data && (
            <button
              type="button"
              onClick={() => setShowExplain((s) => !s)}
              className="rounded-card border border-border bg-surface px-4 py-2 text-sm font-semibold text-primary transition-colors hover:bg-elevated"
            >
              {showExplain
                ? t("predictions.explain_hide", "Hide Explanation")
                : t("predictions.explain_show", "Explain")}
            </button>
          )}
        </div>

        {predict.isError && (
          <div className="flex items-center gap-2 rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
            <AlertCircle className="h-4 w-4" />
            {t(
              "predictions.predict_error",
              "Prediction could not be calculated. There may not be enough model data for the vehicle.",
            )}
          </div>
        )}
      </Card>

      {predict.data && (
        <PredictionResult
          result={{
            tahmini_tuketim: Number(predict.data.tahmini_tuketim ?? 0),
            tahmini_litre: predict.data.prediction_liters as number | undefined,
            model_used:
              (predict.data.model_used as
                | "linear"
                | "xgboost"
                | "ensemble"
                | undefined) ?? "ensemble",
          }}
          mesafeKm={form.mesafe}
        />
      )}

      {predict.data && showExplain && (
        <XaiExplainPanel request={requestPayload} />
      )}
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1 block text-[11px] font-bold uppercase tracking-wider text-secondary">
        {label}
      </label>
      {children}
    </div>
  );
}

function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <Field label={label}>
      <input
        type="number"
        min={0}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="input-base"
      />
    </Field>
  );
}
