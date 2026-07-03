import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Crosshair, Loader2, AlertCircle, CheckCircle2, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { locationService } from "../../api/locations";

interface CalibrationModalProps {
  isOpen: boolean;
  onClose: () => void;
  routeLabel?: string;
}

export function CalibrationModal({
  isOpen,
  onClose,
  routeLabel,
}: CalibrationModalProps) {
  const { t } = useTranslation();
  const [seferIdInput, setSeferIdInput] = useState("");
  const calibrate = useMutation({
    mutationFn: (seferId: number) => locationService.calibrateFromTrip(seferId),
  });

  if (!isOpen) return null;

  const seferId = Number(seferIdInput);
  const isValid =
    seferIdInput.length > 0 && Number.isInteger(seferId) && seferId > 0;
  // Backend error envelope is {"error": {"code", "message", "trace_id"}}
  // (bkz CLAUDE.md) — bir önceki `.data?.detail` okuması gerçek backend'in
  // hiç dönmediği eski/legacy bir şekle bakıyordu, bu yüzden her gerçek
  // 400'de sessizce jenerik fallback mesajına düşüyordu (0-mock epiği Faz2
  // gerçek-backend testinde bulundu).
  const errorDetail =
    (calibrate.error as any)?.response?.data?.error?.message ??
    (calibrate.error as any)?.response?.data?.detail ??
    t("locations.calibration_error");

  const handleClose = () => {
    setSeferIdInput("");
    calibrate.reset();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
      <div className="relative w-full max-w-md overflow-hidden rounded-modal border border-border bg-surface shadow-2xl">
        <div className="flex items-center justify-between border-b border-border bg-elevated/40 p-4">
          <div className="flex items-center gap-2">
            <Crosshair className="h-5 w-5 text-accent" />
            <div>
              <h3 className="text-sm font-semibold text-primary">
                {t("locations.calibration_title")}
              </h3>
              {routeLabel && (
                <p className="text-[11px] font-mono text-secondary">
                  {routeLabel}
                </p>
              )}
            </div>
          </div>
          <button
            onClick={handleClose}
            className="rounded-full p-1.5 text-secondary transition-colors hover:bg-elevated hover:text-primary"
            aria-label={t("common.close")}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4 p-5">
          <p className="text-xs leading-relaxed text-secondary">
            {t("locations.calibration_description")}
          </p>

          <div>
            <label
              htmlFor="calibration-trip-id"
              className="mb-1 block text-[11px] font-bold uppercase tracking-widest text-secondary"
            >
              {t("locations.calibration_trip_id")}
            </label>
            <input
              id="calibration-trip-id"
              type="number"
              min={1}
              value={seferIdInput}
              onChange={(e) => setSeferIdInput(e.target.value)}
              placeholder={t("locations.calibration_trip_placeholder")}
              className="input-base"
              disabled={calibrate.isPending}
            />
            <p className="mt-1 text-[10px] text-tertiary">
              {t("locations.calibration_hint")}
            </p>
          </div>

          {calibrate.isSuccess && calibrate.data?.success && (
            <div className="flex items-center gap-2 rounded-card border border-success/20 bg-success/5 px-4 py-3 text-sm text-success">
              <CheckCircle2 className="h-4 w-4" />
              {calibrate.data.message}
            </div>
          )}

          {calibrate.isError && (
            <div className="flex items-center gap-2 rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
              <AlertCircle className="h-4 w-4" />
              {errorDetail}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={handleClose}
              className="rounded-card px-3 py-1.5 text-xs font-semibold text-secondary transition-colors hover:bg-elevated hover:text-primary"
            >
              {t("common.close")}
            </button>
            <button
              onClick={() => calibrate.mutate(seferId)}
              disabled={!isValid || calibrate.isPending}
              className="inline-flex items-center gap-2 rounded-card bg-accent px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-accent/90 disabled:opacity-50"
            >
              {calibrate.isPending && (
                <Loader2 className="h-3 w-3 animate-spin" />
              )}
              {t("locations.calibrate_btn")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
