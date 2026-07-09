import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ChevronUp, Container, Settings2, X } from "lucide-react";

import { Dorse } from "../../types";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { DORSE_TIPLERI, useTrailerData } from "../../hooks/useTrailerData";
import { useTrailersResources } from "../../resources/useResources";

interface TrailerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: Partial<Dorse>) => Promise<void>;
  trailer: Dorse | null;
}

export function TrailerModal({
  isOpen,
  onClose,
  onSave,
  trailer,
}: TrailerModalProps) {
  const { trailerModalText } = useTrailersResources();
  const {
    showAdvanced,
    setShowAdvanced,
    register,
    handleSubmit,
    errors,
    isSubmitting,
    notes,
    onSubmit,
  } = useTrailerData({ isOpen, onClose, onSave, trailer });

  if (!isOpen) {
    return null;
  }

  // Portal to <body>: VehicleModal'daki aynı desen (bkz. o dosyadaki yorum) —
  // glassmorphism/animasyon ata elemanları position:fixed'i "trap" edebilir.
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
          className="flex max-h-[85vh] w-full max-w-xl flex-col overflow-hidden rounded-modal border border-border bg-surface shadow-xl"
        >
          <div className="flex shrink-0 items-center justify-between border-b border-border bg-elevated p-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-card border border-border bg-elevated text-accent shadow-sm">
                <Container className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-bold tracking-tight text-primary">
                  {trailer
                    ? trailerModalText.title.edit
                    : trailerModalText.title.create}
                </h2>
                <p className="text-xs font-medium text-secondary">
                  {trailer
                    ? trailerModalText.subtitle.edit(trailer.plaka)
                    : trailerModalText.subtitle.create}
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
              <h3 className="text-xs font-bold uppercase tracking-wider text-secondary">
                {trailerModalText.sections.basic}
              </h3>

              <div className="space-y-1.5">
                <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                  {trailerModalText.fields.plate}
                </label>
                <Input
                  {...register("plaka")}
                  placeholder={trailerModalText.placeholders.plate}
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
                    {trailerModalText.fields.brand}
                  </label>
                  <Input
                    {...register("marka")}
                    placeholder={trailerModalText.placeholders.brand}
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
                    {trailerModalText.fields.type}
                  </label>
                  <select
                    {...register("tipi")}
                    className="h-10 w-full rounded-md border border-border bg-elevated px-3 text-sm text-primary outline-none transition-colors focus:border-accent"
                  >
                    {DORSE_TIPLERI.map((tip) => (
                      <option key={tip} value={tip}>
                        {
                          {
                            Standart: trailerModalText.options.standard,
                            Frigo: trailerModalText.options.frigo,
                            Tenteli: trailerModalText.options.tented,
                            Damperli: trailerModalText.options.tipper,
                            Lowbed: trailerModalText.options.lowbed,
                          }[tip]
                        }
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                    {trailerModalText.fields.modelYear}
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
                    {trailerModalText.fields.inspectionDate}
                  </label>
                  <Input type="date" {...register("muayene_tarihi")} />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                    {trailerModalText.fields.emptyWeight}
                  </label>
                  <Input
                    type="number"
                    {...register("bos_agirlik_kg", { valueAsNumber: true })}
                    error={!!errors.bos_agirlik_kg}
                  />
                  {errors.bos_agirlik_kg && (
                    <p className="ml-1 text-xs font-medium text-danger">
                      {errors.bos_agirlik_kg.message}
                    </p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                    {trailerModalText.fields.payload}
                  </label>
                  <Input
                    type="number"
                    {...register("maks_yuk_kapasitesi_kg", {
                      valueAsNumber: true,
                    })}
                    error={!!errors.maks_yuk_kapasitesi_kg}
                  />
                  {errors.maks_yuk_kapasitesi_kg && (
                    <p className="ml-1 text-xs font-medium text-danger">
                      {errors.maks_yuk_kapasitesi_kg.message}
                    </p>
                  )}
                </div>
              </div>

              <div className="space-y-1.5 max-w-[200px]">
                <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                  {trailerModalText.fields.tireCount}
                </label>
                <Input
                  type="number"
                  {...register("lastik_sayisi", { valueAsNumber: true })}
                  error={!!errors.lastik_sayisi}
                />
                {errors.lastik_sayisi && (
                  <p className="ml-1 text-xs font-medium text-danger">
                    {errors.lastik_sayisi.message}
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="ml-1 text-xs font-bold uppercase tracking-wider text-secondary">
                  {trailerModalText.fields.notes}
                </label>
                <textarea
                  {...register("notlar")}
                  placeholder={trailerModalText.placeholders.notes}
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
                    {trailerModalText.fields.active}
                  </span>
                  <p className="text-xs text-secondary">
                    {trailerModalText.fields.activeDescription}
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
                      {trailerModalText.sections.technical}
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
                      <p className="text-xs font-medium text-secondary">
                        {trailerModalText.fields.advancedCoefficients}
                      </p>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1">
                          <label className="text-xs font-medium text-secondary">
                            {trailerModalText.fields.rollingResistance}
                          </label>
                          <Input
                            type="number"
                            step="0.001"
                            {...register("dorse_lastik_direnc_katsayisi", {
                              valueAsNumber: true,
                            })}
                            error={!!errors.dorse_lastik_direnc_katsayisi}
                          />
                          {errors.dorse_lastik_direnc_katsayisi && (
                            <p className="text-xs font-medium text-danger">
                              {errors.dorse_lastik_direnc_katsayisi.message}
                            </p>
                          )}
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs font-medium text-secondary">
                            {trailerModalText.fields.dragContribution}
                          </label>
                          <Input
                            type="number"
                            step="0.01"
                            {...register("dorse_hava_direnci", {
                              valueAsNumber: true,
                            })}
                            error={!!errors.dorse_hava_direnci}
                          />
                          {errors.dorse_hava_direnci && (
                            <p className="text-xs font-medium text-danger">
                              {errors.dorse_hava_direnci.message}
                            </p>
                          )}
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
                  {trailerModalText.actions.cancel}
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  className="h-9 flex-1"
                  isLoading={isSubmitting}
                >
                  {trailer
                    ? trailerModalText.actions.update
                    : trailerModalText.actions.save}
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
