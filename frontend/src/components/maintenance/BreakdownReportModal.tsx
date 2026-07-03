import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { vehicleService } from "@/api/vehicles";
import { dorseService } from "@/services/dorseService";
import axiosInstance from "@/services/api/axios-instance";
import { useNotify } from "@/context/NotificationContext";
import { useMaintenancePredictionsResources } from "@/resources/useResources";

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

/**
 * Operatör/sürücü "Arıza Bildir" hızlı formu. İzin gerektirmez — araç VEYA
 * dorse için açık ARIZA/ACIL kaydı oluşturur (POST /maintenance/report-breakdown).
 */
export function BreakdownReportModal({ isOpen, onClose }: Props) {
  const { notify } = useNotify();
  const { maintenancePredictionsText } = useMaintenancePredictionsResources();
  const txt = maintenancePredictionsText.breakdown;
  const qc = useQueryClient();
  const [target, setTarget] = useState<"arac" | "dorse">("arac");
  const [aracId, setAracId] = useState("");
  const [dorseId, setDorseId] = useState("");
  const [tip, setTip] = useState<"ARIZA" | "ACIL">("ARIZA");
  const [detaylar, setDetaylar] = useState("");
  const [km, setKm] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: vehiclesResp } = useQuery({
    queryKey: ["vehiclesForBreakdown"],
    queryFn: () => vehicleService.getAll({ limit: 500 }),
    enabled: isOpen,
    staleTime: 5 * 60 * 1000,
  });
  const vehicles = vehiclesResp?.items ?? [];

  const { data: dorseList } = useQuery({
    queryKey: ["dorsesForBreakdown"],
    queryFn: () => dorseService.getAll({ aktif_only: true }),
    enabled: isOpen,
    staleTime: 5 * 60 * 1000,
  });
  const dorses = dorseList ?? [];

  const reset = () => {
    setTarget("arac");
    setAracId("");
    setDorseId("");
    setTip("ARIZA");
    setDetaylar("");
    setKm("");
    setError(null);
  };

  const mutation = useMutation({
    mutationFn: () =>
      axiosInstance.post("/maintenance/report-breakdown", {
        ...(target === "arac"
          ? { arac_id: Number(aracId) }
          : { dorse_id: Number(dorseId) }),
        bakim_tipi: tip,
        detaylar: detaylar.trim(),
        km_bilgisi: Number(km || 0),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["adminMaintenanceAlerts"] });
      notify("success", txt.successTitle, txt.successBody);
      reset();
      onClose();
    },
    onError: (err: unknown) => {
      const data = (
        err as {
          response?: {
            data?: { detail?: string; error?: { message?: string } };
          };
        }
      )?.response?.data;
      const detail = data?.error?.message ?? data?.detail ?? txt.errGeneric;
      setError(typeof detail === "string" ? detail : txt.errGeneric);
    },
  });

  const submit = () => {
    setError(null);
    if (target === "arac" && !aracId) {
      setError(txt.errVehicleRequired);
      return;
    }
    if (target === "dorse" && !dorseId) {
      setError(txt.errTrailerRequired);
      return;
    }
    mutation.mutate();
  };

  const inputCls =
    "w-full rounded-xl border border-border bg-base px-4 py-3 text-primary transition-all focus:border-accent focus:outline-none";
  const toggleCls = (active: boolean) =>
    `flex-1 rounded-xl border px-4 py-2.5 text-sm font-bold transition-all ${
      active
        ? "border-accent bg-accent-soft text-accent"
        : "border-border text-secondary hover:bg-elevated"
    }`;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <span className="flex items-center gap-2 text-danger">
          <AlertTriangle className="h-5 w-5" />
          {txt.title}
        </span>
      }
    >
      <div className="space-y-4">
        <div className="space-y-1.5">
          <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
            {txt.targetLabel}
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setTarget("arac")}
              className={toggleCls(target === "arac")}
            >
              {txt.vehicle}
            </button>
            <button
              type="button"
              onClick={() => setTarget("dorse")}
              className={toggleCls(target === "dorse")}
            >
              {txt.trailer}
            </button>
          </div>
        </div>

        {target === "arac" ? (
          <div className="space-y-1.5">
            <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
              {txt.vehicle}
            </label>
            <select
              value={aracId}
              onChange={(e) => setAracId(e.target.value)}
              className={inputCls}
            >
              <option value="">{txt.selectVehicle}</option>
              {vehicles.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.plaka} {v.marka ? `— ${v.marka}` : ""}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="space-y-1.5">
            <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
              {txt.trailer}
            </label>
            <select
              value={dorseId}
              onChange={(e) => setDorseId(e.target.value)}
              className={inputCls}
            >
              <option value="">{txt.selectTrailer}</option>
              {dorses.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.plaka} {d.tipi ? `— ${d.tipi}` : ""}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="space-y-1.5">
          <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
            {txt.urgencyLabel}
          </label>
          <div className="flex gap-2">
            {(["ARIZA", "ACIL"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTip(t)}
                className={`flex-1 rounded-xl border px-4 py-2.5 text-sm font-bold transition-all ${
                  tip === t
                    ? t === "ACIL"
                      ? "border-danger bg-danger/10 text-danger"
                      : "border-warning bg-warning/10 text-warning"
                    : "border-border text-secondary hover:bg-elevated"
                }`}
              >
                {t === "ACIL" ? txt.urgent : txt.fault}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-1.5">
          <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
            {txt.kmLabel}
          </label>
          <input
            type="number"
            value={km}
            onChange={(e) => setKm(e.target.value)}
            placeholder="0"
            className={inputCls}
          />
        </div>

        <div className="space-y-1.5">
          <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
            {txt.descriptionLabel}
          </label>
          <textarea
            value={detaylar}
            onChange={(e) => setDetaylar(e.target.value)}
            rows={3}
            placeholder={txt.descriptionPlaceholder}
            className={inputCls}
          />
        </div>

        {error && <p className="text-sm font-medium text-danger">{error}</p>}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onClose}>
            {txt.cancel}
          </Button>
          <Button onClick={submit} disabled={mutation.isPending}>
            {mutation.isPending ? txt.submitting : txt.submit}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
