import { useEffect, useState } from "react";

import { AnimatePresence, motion } from "framer-motion";
import { Info, Save, X } from "lucide-react";

import { Dorse } from "../../types";
import { Button } from "../ui/Button";
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
  const [formData, setFormData] = useState<Partial<Dorse>>({
    plaka: "",
    marka: "",
    tipi: "Standart",
    yil: new Date().getFullYear(),
    bos_agirlik_kg: 6000,
    maks_yuk_kapasitesi_kg: 24000,
    lastik_sayisi: 6,
    dorse_lastik_direnc_katsayisi: 0.006,
    dorse_hava_direnci: 0.2,
    aktif: true,
    notlar: "",
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (trailer) {
      setFormData(trailer);
      return;
    }

    setFormData({
      plaka: "",
      marka: "",
      tipi: "Standart",
      yil: new Date().getFullYear(),
      bos_agirlik_kg: 6000,
      maks_yuk_kapasitesi_kg: 24000,
      lastik_sayisi: 6,
      dorse_lastik_direnc_katsayisi: 0.006,
      dorse_hava_direnci: 0.2,
      aktif: true,
      notlar: "",
    });
  }, [trailer, isOpen]);

  if (!isOpen) {
    return null;
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    try {
      await onSave(formData);
      onClose();
    } catch (saveError) {
      console.error("Trailer save error:", saveError);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (
    event: React.ChangeEvent<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >,
  ) => {
    const { name, value, type } = event.target;
    setFormData((previous) => ({
      ...previous,
      [name]:
        type === "number" ? (value === "" ? 0 : parseFloat(value)) : value,
    }));
  };

  const handleCheckboxChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, checked } = event.target;
    setFormData((previous) => ({
      ...previous,
      [name]: checked,
    }));
  };

  const handleFocus = (event: React.FocusEvent<HTMLInputElement>) => {
    if (event.target.type === "number") {
      event.target.select();
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        />

        <motion.div
          initial={{ scale: 0.9, opacity: 0, y: 20 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.9, opacity: 0, y: 20 }}
          className="relative flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-[32px] border border-accent/20 bg-surface shadow-lg"
        >
          <div className="flex shrink-0 items-center justify-between border-b border-border bg-gradient-to-r from-accent/5 to-transparent p-8">
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-primary">
                {trailer
                  ? trailerModalText.title.edit
                  : trailerModalText.title.create}
              </h2>
              <p className="mt-1 text-xs font-medium uppercase tracking-widest text-secondary">
                {trailer
                  ? trailerModalText.subtitle.edit(trailer.id, trailer.plaka)
                  : trailerModalText.subtitle.create}
              </p>
            </div>
            <button
              onClick={onClose}
              className="rounded-2xl bg-elevated p-3 text-secondary transition-all hover:bg-danger/10 hover:text-primary"
            >
              <X className="h-6 w-6" />
            </button>
          </div>

          <form
            onSubmit={handleSubmit}
            className="custom-scrollbar min-h-0 flex-1 overflow-y-auto p-8"
          >
            <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
              <div className="space-y-6">
                <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-accent">
                  <div className="h-1.5 w-1.5 rounded-full bg-accent" />
                  {trailerModalText.sections.basic}
                </h3>

                <div className="space-y-4">
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-secondary">
                      {trailerModalText.fields.plate}
                    </label>
                    <input
                      type="text"
                      name="plaka"
                      value={formData.plaka}
                      onChange={handleChange}
                      required
                      className="w-full rounded-xl border border-border bg-base px-4 py-3 font-bold tracking-tight text-primary transition-all focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/10"
                      placeholder={trailerModalText.placeholders.plate}
                    />
                  </div>

                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-secondary">
                      {trailerModalText.fields.brand}
                    </label>
                    <input
                      type="text"
                      name="marka"
                      value={formData.marka ?? ""}
                      onChange={handleChange}
                      className="w-full rounded-xl border border-border bg-base px-4 py-3 text-primary transition-all focus:border-accent focus:outline-none"
                      placeholder={trailerModalText.placeholders.brand}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-secondary">
                        {trailerModalText.fields.type}
                      </label>
                      <select
                        name="tipi"
                        value={formData.tipi}
                        onChange={handleChange}
                        className="w-full rounded-xl border border-border bg-base px-4 py-3 text-primary transition-all focus:border-accent focus:outline-none"
                      >
                        <option value="Standart">
                          {trailerModalText.options.standard}
                        </option>
                        <option value="Frigo">
                          {trailerModalText.options.frigo}
                        </option>
                        <option value="Tenteli">
                          {trailerModalText.options.tented}
                        </option>
                        <option value="Damperli">
                          {trailerModalText.options.tipper}
                        </option>
                        <option value="Lowbed">
                          {trailerModalText.options.lowbed}
                        </option>
                      </select>
                    </div>
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-secondary">
                        {trailerModalText.fields.modelYear}
                      </label>
                      <input
                        type="number"
                        name="yil"
                        value={formData.yil ?? ""}
                        onChange={handleChange}
                        className="w-full rounded-xl border border-border bg-base px-4 py-3 text-primary transition-all focus:border-accent focus:outline-none"
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="space-y-6">
                <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-accent">
                  <div className="h-1.5 w-1.5 rounded-full bg-accent" />
                  {trailerModalText.sections.technical}
                </h3>

                <div className="space-y-4 rounded-2xl border border-border bg-elevated p-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="mb-2 block text-[10px] font-bold uppercase tracking-wider text-secondary">
                        {trailerModalText.fields.emptyWeight}
                      </label>
                      <input
                        type="number"
                        name="bos_agirlik_kg"
                        value={formData.bos_agirlik_kg}
                        onChange={handleChange}
                        onFocus={handleFocus}
                        className="w-full rounded-xl border border-border bg-base px-3 py-2 text-sm text-primary transition-all focus:border-accent focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-[10px] font-bold uppercase tracking-wider text-secondary">
                        {trailerModalText.fields.payload}
                      </label>
                      <input
                        type="number"
                        name="maks_yuk_kapasitesi_kg"
                        value={formData.maks_yuk_kapasitesi_kg}
                        onChange={handleChange}
                        onFocus={handleFocus}
                        className="w-full rounded-xl border border-border bg-base px-3 py-2 text-sm text-primary transition-all focus:border-accent focus:outline-none"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="mb-2 block text-[10px] font-bold uppercase tracking-wider text-secondary">
                      {trailerModalText.fields.tireCount}
                    </label>
                    <input
                      type="number"
                      name="lastik_sayisi"
                      value={formData.lastik_sayisi}
                      onChange={handleChange}
                      onFocus={handleFocus}
                      className="w-full rounded-xl border border-border bg-base px-3 py-2 text-sm text-primary transition-all focus:border-accent focus:outline-none"
                    />
                  </div>

                  <div className="pt-2">
                    <div className="mb-2 flex items-center gap-2">
                      <Info className="h-3 w-3 text-secondary" />
                      <span className="text-[10px] font-medium uppercase tracking-widest text-secondary">
                        {trailerModalText.fields.advancedCoefficients}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="mb-1 block text-[9px] font-bold uppercase tracking-wider text-secondary/60">
                          {trailerModalText.fields.rollingResistance}
                        </label>
                        <input
                          type="number"
                          step="0.001"
                          name="dorse_lastik_direnc_katsayisi"
                          value={formData.dorse_lastik_direnc_katsayisi ?? ""}
                          onChange={handleChange}
                          onFocus={handleFocus}
                          className="w-full rounded-lg border border-border border-dashed bg-base px-3 py-1.5 text-xs text-primary focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-[9px] font-bold uppercase tracking-wider text-secondary/40">
                          {trailerModalText.fields.dragContribution}
                        </label>
                        <input
                          type="number"
                          step="0.01"
                          name="dorse_hava_direnci"
                          value={formData.dorse_hava_direnci ?? ""}
                          onChange={handleChange}
                          onFocus={handleFocus}
                          className="w-full rounded-lg border border-border border-dashed bg-base px-3 py-1.5 text-xs text-primary focus:outline-none"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-8 grid grid-cols-1 gap-8 border-t border-border pt-8 md:grid-cols-2">
              <div>
                <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-secondary">
                  {trailerModalText.fields.notes}
                </label>
                <textarea
                  name="notlar"
                  value={formData.notlar ?? ""}
                  onChange={handleChange}
                  rows={3}
                  className="w-full resize-none rounded-xl border border-border bg-base px-4 py-3 text-sm text-primary transition-all focus:border-accent focus:outline-none"
                  placeholder={trailerModalText.placeholders.notes}
                />
              </div>
              <div className="flex items-end pb-4">
                <label className="flex w-full cursor-pointer items-center gap-4 rounded-2xl border border-border bg-elevated p-4 transition-all hover:bg-accent/5">
                  <div className="relative inline-flex cursor-pointer items-center">
                    <input
                      type="checkbox"
                      name="aktif"
                      checked={formData.aktif}
                      onChange={handleCheckboxChange}
                      className="peer sr-only"
                    />
                    <div className="h-6 w-11 rounded-full bg-secondary/20 peer-checked:bg-accent peer-checked:after:translate-x-full peer-checked:after:border-bg-surface peer-focus:outline-none after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:border after:border-border after:bg-base after:transition-all after:content-['']" />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-sm font-bold tracking-tight text-primary uppercase">
                      {trailerModalText.fields.active}
                    </span>
                    <span className="text-[10px] text-secondary">
                      {trailerModalText.fields.activeDescription}
                    </span>
                  </div>
                </label>
              </div>
            </div>
          </form>

          <div className="flex items-center justify-between border-t border-border bg-surface/80 p-8 backdrop-blur-xl">
            <Button
              variant="ghost"
              onClick={onClose}
              className="text-primary hover:bg-elevated"
            >
              {trailerModalText.actions.cancel}
            </Button>
            <Button
              variant="primary"
              onClick={handleSubmit}
              disabled={loading}
              className="gap-2 bg-accent px-10 shadow-lg hover:bg-accent-dark"
            >
              {loading ? (
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-bg-base/30 border-t-bg-base" />
              ) : (
                <>
                  <Save className="h-5 w-5" />
                  {trailer
                    ? trailerModalText.actions.update
                    : trailerModalText.actions.save}
                </>
              )}
            </Button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
