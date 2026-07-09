import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ChevronUp, Settings2 } from "lucide-react";

import { Dorse } from "../../types";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Modal } from "../ui/Modal";
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

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        trailer ? trailerModalText.title.edit : trailerModalText.title.create
      }
    >
      <p className="mb-6 text-sm text-secondary">
        {trailer
          ? trailerModalText.subtitle.edit(trailer.plaka)
          : trailerModalText.subtitle.create}
      </p>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
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

        <div className="max-w-[200px] space-y-1.5">
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

        <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-border bg-elevated/30 p-3 transition-colors hover:bg-elevated">
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

        <div className="overflow-hidden rounded-xl border border-border bg-elevated/20">
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

        <div className="relative z-10 mt-4 flex w-full items-center justify-between gap-4 border-t border-border/20 pt-8">
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            className="h-14 rounded-xl bg-elevated px-8 text-[10px] font-black uppercase tracking-widest text-tertiary border-border/40 hover:bg-surface hover:text-primary"
          >
            {trailerModalText.actions.cancel}
          </Button>
          <Button
            type="submit"
            variant="primary"
            isLoading={isSubmitting}
            className="h-14 rounded-xl px-12 text-[10px] font-black uppercase tracking-[0.2em] shadow-2xl shadow-accent/20 hover:shadow-accent/40"
          >
            {trailer
              ? trailerModalText.actions.update
              : trailerModalText.actions.save}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
