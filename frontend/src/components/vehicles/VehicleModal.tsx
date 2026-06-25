import { AnimatePresence, motion } from "framer-motion";
import { createPortal } from "react-dom";
import { ChevronDown, ChevronUp, Settings2, Truck, X } from "lucide-react";

import { Vehicle } from "../../types";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { useVehicleData, YAKIT_TIPLERI } from "../../hooks/useVehicleData";
import { useVehiclesResources } from "../../resources/useResources";
import { useTranslation } from "react-i18next";

interface VehicleModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (vehicle: Partial<Vehicle>) => Promise<void>;
  vehicle?: Vehicle | null;
}

export function VehicleModal({
  isOpen,
  onClose,
  onSave,
  vehicle,
}: VehicleModalProps) {
  const { t } = useTranslation();
  const { vehicleModalText } = useVehiclesResources();
  const {
    showAdvanced,
    setShowAdvanced,
    register,
    handleSubmit,
    errors,
    isSubmitting,
    notes,
    onSubmit,
  } = useVehicleData({ isOpen, onClose, onSave, vehicle });

  if (!isOpen) {
    return null;
  }

  // Portal to <body>: the modal uses position:fixed, but glassmorphism
  // ancestors (.glass → backdrop-filter) and animated wrappers create
  // containing blocks that trap fixed positioning, mispositioning the modal
  // (overflowed the viewport, submit below the fold). A body portal escapes them.
  return createPortal(
    <AnimatePresence>
      <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        />
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="flex max-h-[85vh] w-full max-w-xl flex-col overflow-hidden rounded-[12px] border border-border bg-surface shadow-xl"
        >
          <div className="flex shrink-0 items-center justify-between border-b border-border bg-elevated p-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-[10px] border border-border bg-elevated text-accent shadow-sm">
                <Truck className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-bold tracking-tight text-primary">
                  {vehicle
                    ? vehicleModalText.title.edit
                    : vehicleModalText.title.create}
                </h2>
                <p className="text-xs font-medium text-secondary">
                  {vehicle
                    ? vehicleModalText.description.edit
                    : vehicleModalText.description.create}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="rounded-full p-2 text-secondary transition-colors hover:bg-surface hover:text-primary"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <form
            onSubmit={handleSubmit(onSubmit)}
            className="flex flex-1 flex-col overflow-hidden"
          >
            <div className="custom-scrollbar flex-1 space-y-5 overflow-y-auto bg-surface p-6">
              <div className="space-y-1.5">
                <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                  {vehicleModalText.fields.plate}
                </label>
                <Input
                  {...register("plaka")}
                  placeholder={vehicleModalText.placeholders.plate}
                  className="font-mono text-lg uppercase tracking-wider"
                  error={!!errors.plaka}
                />
                {errors.plaka && (
                  <p className="ml-1 text-xs font-medium text-danger">
                    {errors.plaka.message}
                  </p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                    {vehicleModalText.fields.brand}
                  </label>
                  <Input
                    {...register("marka")}
                    placeholder={vehicleModalText.placeholders.brand}
                    error={!!errors.marka}
                  />
                  {errors.marka && (
                    <p className="ml-1 text-xs font-medium text-danger">
                      {errors.marka.message}
                    </p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                    {vehicleModalText.fields.model}
                  </label>
                  <Input
                    {...register("model")}
                    placeholder={vehicleModalText.placeholders.model}
                    error={!!errors.model}
                  />
                  {errors.model && (
                    <p className="ml-1 text-xs font-medium text-danger">
                      {errors.model.message}
                    </p>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                    {vehicleModalText.fields.year}
                  </label>
                  <Input
                    type="number"
                    {...register("yil", { valueAsNumber: true })}
                    error={!!errors.yil}
                  />
                  {errors.yil && (
                    <p className="ml-1 text-xs font-medium text-danger">
                      {errors.yil.message}
                    </p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                    {vehicleModalText.fields.tankCapacity}
                  </label>
                  <div className="relative">
                    <Input
                      type="number"
                      {...register("tank_kapasitesi", {
                        valueAsNumber: true,
                      })}
                      className="pr-8"
                      error={!!errors.tank_kapasitesi}
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm font-medium text-secondary">
                      L
                    </span>
                  </div>
                  {errors.tank_kapasitesi && (
                    <p className="ml-1 text-xs font-medium text-danger">
                      {errors.tank_kapasitesi.message}
                    </p>
                  )}
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                  {vehicleModalText.fields.targetConsumption}
                </label>
                <div className="relative max-w-[200px]">
                  <Input
                    type="number"
                    step="0.1"
                    {...register("hedef_tuketim", {
                      valueAsNumber: true,
                    })}
                    className="pr-20"
                    error={!!errors.hedef_tuketim}
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-medium text-secondary">
                    L/100km
                  </span>
                </div>
                {errors.hedef_tuketim && (
                  <p className="ml-1 text-xs font-medium text-danger">
                    {errors.hedef_tuketim.message}
                  </p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                    {t("fleet.fuel_type_label")}
                  </label>
                  <select
                    {...register("yakit_tipi")}
                    className="h-10 w-full rounded-md border border-border bg-elevated px-3 text-sm text-primary outline-none transition-colors focus:border-accent"
                  >
                    {YAKIT_TIPLERI.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                    {t("fleet.axle_count_label")}
                  </label>
                  <Input
                    type="number"
                    min={1}
                    max={10}
                    {...register("dingil_sayisi", { valueAsNumber: true })}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                  {t("fleet.inspection_validity_label")}
                </label>
                <Input type="date" {...register("muayene_tarihi")} />
              </div>

              <div className="space-y-1.5">
                <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                  {t("fleet.insurance_validity_label")}
                </label>
                <Input
                  type="date"
                  {...register("sigorta_tarihi")}
                  error={!!errors.sigorta_tarihi}
                />
                {errors.sigorta_tarihi && (
                  <p className="ml-1 text-xs font-medium text-danger">
                    {errors.sigorta_tarihi.message}
                  </p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                    {t("fleet.engine_no_label")}
                  </label>
                  <Input
                    {...register("motor_no")}
                    placeholder={t("fleet.engine_no_placeholder")}
                    className="border-transparent bg-elevated/50 text-primary focus:border-border"
                    error={!!errors.motor_no}
                  />
                  {errors.motor_no && (
                    <p className="ml-1 text-xs font-medium text-danger">
                      {errors.motor_no.message}
                    </p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                    {t("fleet.chassis_no_label")}
                  </label>
                  <Input
                    {...register("sasi_no")}
                    placeholder={t("fleet.chassis_no_placeholder")}
                    className="border-transparent bg-elevated/50 text-primary focus:border-border"
                    error={!!errors.sasi_no}
                  />
                  {errors.sasi_no && (
                    <p className="ml-1 text-xs font-medium text-danger">
                      {errors.sasi_no.message}
                    </p>
                  )}
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                  {vehicleModalText.fields.notes}
                </label>
                <textarea
                  {...register("notlar")}
                  placeholder={vehicleModalText.placeholders.notes}
                  rows={2}
                  className="flex w-full resize-none rounded-md border border-border bg-elevated px-3 py-2 text-sm text-primary transition-colors placeholder:text-secondary focus-visible:border-accent focus-visible:outline-none"
                />
                <p className="text-right text-xs text-secondary">
                  {notes.length}/500
                </p>
              </div>

              <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-border bg-surface p-3 transition-colors hover:bg-elevated">
                <input
                  type="checkbox"
                  {...register("aktif")}
                  className="h-5 w-5 rounded border-border bg-elevated text-accent focus:ring-accent"
                />
                <div>
                  <span className="text-sm font-bold text-primary">
                    {vehicleModalText.fields.active}
                  </span>
                  <p className="text-xs text-secondary">
                    {vehicleModalText.fields.activeDescription}
                  </p>
                </div>
              </label>

              <div className="overflow-hidden rounded-xl border border-border bg-surface">
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="flex w-full items-center justify-between p-4 transition-colors hover:bg-elevated"
                >
                  <div className="flex items-center gap-2">
                    <Settings2 className="h-4 w-4 text-primary" />
                    <span className="text-sm font-bold text-primary">
                      {vehicleModalText.fields.physics}
                    </span>
                  </div>
                  {showAdvanced ? (
                    <ChevronUp className="h-4 w-4 text-secondary" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-secondary" />
                  )}
                </button>
                <AnimatePresence>
                  {showAdvanced && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="space-y-4 border-t border-border bg-elevated p-4"
                    >
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1">
                          <label className="text-xs font-medium text-secondary">
                            {vehicleModalText.fields.emptyWeight}
                          </label>
                          <Input
                            type="number"
                            {...register("bos_agirlik_kg", {
                              valueAsNumber: true,
                            })}
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs font-medium text-secondary">
                            {vehicleModalText.fields.dragCoefficient}
                          </label>
                          <Input
                            type="number"
                            step="0.01"
                            {...register("hava_direnc_katsayisi", {
                              valueAsNumber: true,
                            })}
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs font-medium text-secondary">
                            {vehicleModalText.fields.frontalArea}
                          </label>
                          <Input
                            type="number"
                            step="0.1"
                            {...register("on_kesit_alani_m2", {
                              valueAsNumber: true,
                            })}
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs font-medium text-secondary">
                            {vehicleModalText.fields.engineEfficiency}
                          </label>
                          <Input
                            type="number"
                            step="0.01"
                            {...register("motor_verimliligi", {
                              valueAsNumber: true,
                            })}
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs font-medium text-secondary">
                            {vehicleModalText.fields.rollingResistance}
                          </label>
                          <Input
                            type="number"
                            step="0.001"
                            {...register("lastik_direnc_katsayisi", {
                              valueAsNumber: true,
                            })}
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs font-medium text-secondary">
                            {vehicleModalText.fields.maxPayload}
                          </label>
                          <Input
                            type="number"
                            {...register("maks_yuk_kapasitesi_kg", {
                              valueAsNumber: true,
                            })}
                          />
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>

            <div className="shrink-0 border-t border-border bg-elevated/30 p-6">
              <div className="flex gap-4">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={onClose}
                  className="flex-1"
                >
                  {vehicleModalText.actions.cancel}
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  className="h-9 flex-1"
                  isLoading={isSubmitting}
                >
                  {vehicle
                    ? vehicleModalText.actions.update
                    : vehicleModalText.actions.create}
                </Button>
              </div>
            </div>
          </form>
        </motion.div>
      </div>
    </AnimatePresence>,
    document.body,
  );
}
