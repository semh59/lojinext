import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { vehicleService } from "@/api/vehicles";
import axiosInstance from "@/services/api/axios-instance";
import { useNotify } from "@/context/NotificationContext";

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

/**
 * Operatör/sürücü "Arıza Bildir" hızlı formu. İzin gerektirmez — açık
 * ARIZA/ACIL kaydı oluşturur (POST /maintenance/report-breakdown).
 */
export function BreakdownReportModal({ isOpen, onClose }: Props) {
  const { notify } = useNotify();
  const qc = useQueryClient();
  const [aracId, setAracId] = useState("");
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

  const reset = () => {
    setAracId("");
    setTip("ARIZA");
    setDetaylar("");
    setKm("");
    setError(null);
  };

  const mutation = useMutation({
    mutationFn: () =>
      axiosInstance.post("/maintenance/report-breakdown", {
        arac_id: Number(aracId),
        bakim_tipi: tip,
        detaylar: detaylar.trim(),
        km_bilgisi: Number(km || 0),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["adminMaintenanceAlerts"] });
      notify("success", "Arıza bildirildi", "Açık arıza kaydı oluşturuldu.");
      reset();
      onClose();
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Arıza bildirilemedi.";
      setError(typeof detail === "string" ? detail : "Arıza bildirilemedi.");
    },
  });

  const submit = () => {
    setError(null);
    if (!aracId) {
      setError("Araç seçiniz.");
      return;
    }
    mutation.mutate();
  };

  const inputCls =
    "w-full rounded-xl border border-border bg-base px-4 py-3 text-primary transition-all focus:border-accent focus:outline-none";

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <span className="flex items-center gap-2 text-danger">
          <AlertTriangle className="h-5 w-5" />
          Arıza Bildir
        </span>
      }
    >
      <div className="space-y-4">
        <div className="space-y-1.5">
          <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
            Araç
          </label>
          <select
            value={aracId}
            onChange={(e) => setAracId(e.target.value)}
            className={inputCls}
          >
            <option value="">Araç seçiniz…</option>
            {vehicles.map((v) => (
              <option key={v.id} value={v.id}>
                {v.plaka} {v.marka ? `— ${v.marka}` : ""}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1.5">
          <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
            Aciliyet
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
                {t === "ACIL" ? "Acil" : "Arıza"}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
              KM (opsiyonel)
            </label>
            <input
              type="number"
              value={km}
              onChange={(e) => setKm(e.target.value)}
              placeholder="0"
              className={inputCls}
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
            Açıklama
          </label>
          <textarea
            value={detaylar}
            onChange={(e) => setDetaylar(e.target.value)}
            rows={3}
            placeholder="Arıza nedir?"
            className={inputCls}
          />
        </div>

        {error && <p className="text-sm font-medium text-danger">{error}</p>}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onClose}>
            İptal
          </Button>
          <Button onClick={submit} disabled={mutation.isPending}>
            {mutation.isPending ? "Gönderiliyor…" : "Bildir"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
