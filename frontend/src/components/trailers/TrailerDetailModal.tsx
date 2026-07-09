import { useState } from "react";

import { AnimatePresence, motion } from "framer-motion";
import {
  Calendar,
  CircleDot,
  Hash,
  Info,
  type LucideIcon,
  Settings,
  Tractor,
  Truck,
  Weight,
  X,
} from "lucide-react";

import { Dorse } from "../../types";
import { useTrailersResources } from "../../resources/useResources";
import { useLocale } from "../../hooks/useLocale";
interface TrailerDetailModalProps {
  trailer: Dorse | null;
  onClose: () => void;
}

type DetailTab = "general" | "technical" | "maintenance";

const fallbackValue = "-";

const InfoCard = ({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
}) => (
  <div className="group flex items-center gap-4 rounded-2xl border border-border bg-elevated/20 p-4 transition-all hover:bg-elevated/40">
    <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-elevated text-secondary transition-colors group-hover:text-accent">
      <Icon size={20} />
    </div>
    <div>
      <p className="mb-0.5 text-xs font-medium uppercase tracking-wider text-secondary">
        {label}
      </p>
      <p className="text-sm font-bold text-primary transition-colors group-hover:text-accent">
        {value}
      </p>
    </div>
  </div>
);

const safeMetric = (
  value: number | null | undefined,
  locale: string,
  unit?: string,
) =>
  value == null
    ? fallbackValue
    : `${value.toLocaleString(locale)}${unit ? ` ${unit}` : ""}`;

const safeText = (value?: string | null) => value || fallbackValue;

const safeNullableText = (value?: string | null, unspecified = fallbackValue) =>
  value || unspecified;

const TrailerDetailModal = ({ trailer, onClose }: TrailerDetailModalProps) => {
  const { trailerDetailText } = useTrailersResources();
  const locale = useLocale();
  const tabs: Array<{ id: DetailTab; label: string; icon: LucideIcon }> = [
    { id: "general", label: trailerDetailText.tabs.general, icon: Info },
    {
      id: "technical",
      label: trailerDetailText.tabs.technical,
      icon: Settings,
    },
    {
      id: "maintenance",
      label: trailerDetailText.tabs.maintenance,
      icon: Truck,
    },
  ];
  const [activeTab, setActiveTab] = useState<DetailTab>("general");

  if (!trailer) {
    return null;
  }

  // Overlay'de backdrop-blur-sm KULLANILMIYOR (2026-07-09 saydamlık
  // bulgusu, bkz. VehicleModal.tsx/TrailerModal.tsx aynı yorum): Chromium
  // bu blur'u panel sibling'ine sızdırıyor, panel tam opak olsa da
  // bulanık/saydam render ediliyor.
  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="absolute inset-0 bg-black/60"
        />

        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          className="relative w-full max-w-4xl overflow-hidden rounded-3xl border border-border bg-surface shadow-2xl"
        >
          <div className="relative flex h-48 items-end bg-gradient-to-br from-accent/20 to-accent/5 p-8">
            <div className="absolute right-6 top-6">
              <button
                onClick={onClose}
                className="rounded-xl p-2 text-secondary transition-colors hover:bg-elevated hover:text-primary"
              >
                <X size={24} />
              </button>
            </div>

            <div className="flex items-center gap-6">
              <div className="flex h-24 w-24 shrink-0 items-center justify-center rounded-2xl border border-accent/30 bg-accent/20 text-accent">
                <Tractor size={48} />
              </div>
              <div>
                <h2 className="text-3xl font-bold tracking-tight text-primary">
                  {trailer.plaka}
                </h2>
                <p className="font-medium text-accent">
                  {trailer.marka} {trailer.model}
                </p>
              </div>
            </div>

            <div className="absolute bottom-8 right-8">
              <div
                className={`rounded-full border px-4 py-1.5 text-xs font-bold uppercase tracking-wider ${
                  trailer.aktif
                    ? "border-success/30 bg-success/10 text-success"
                    : "border-danger/30 bg-danger/10 text-danger"
                }`}
              >
                {trailer.aktif
                  ? trailerDetailText.status.active
                  : trailerDetailText.status.inactive}
              </div>
            </div>
          </div>

          <div className="flex border-b border-border px-8">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`relative flex items-center gap-2 px-6 py-4 text-sm font-medium transition-all ${
                  activeTab === tab.id
                    ? "text-accent"
                    : "text-secondary hover:text-primary"
                }`}
              >
                <tab.icon size={18} />
                {tab.label}
                {activeTab === tab.id && (
                  <motion.div
                    layoutId="activeTrailerTab"
                    className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent shadow-[0_0_10px_rgba(var(--accent-rgb),0.5)]"
                  />
                )}
              </button>
            ))}
          </div>

          <div className="custom-scrollbar max-h-[500px] overflow-y-auto p-8">
            {activeTab === "general" && (
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                <div className="space-y-6">
                  <h3 className="px-1 text-xs font-bold uppercase tracking-widest text-secondary">
                    {trailerDetailText.sections.basic}
                  </h3>
                  <div className="grid grid-cols-1 gap-4">
                    <InfoCard
                      icon={Hash}
                      label={trailerDetailText.fields.plate}
                      value={trailer.plaka}
                    />
                    <InfoCard
                      icon={Truck}
                      label={trailerDetailText.fields.brandModel}
                      value={`${safeText(trailer.marka)} ${safeText(
                        trailer.model,
                      )}`.trim()}
                    />
                    <InfoCard
                      icon={Calendar}
                      label={trailerDetailText.fields.modelYear}
                      value={trailer.yil?.toString() || fallbackValue}
                    />
                  </div>
                </div>
                <div className="space-y-6">
                  <h3 className="px-1 text-xs font-bold uppercase tracking-widest text-secondary">
                    {trailerDetailText.sections.operational}
                  </h3>
                  <div className="grid grid-cols-1 gap-4">
                    <InfoCard
                      icon={CircleDot}
                      label={trailerDetailText.fields.type}
                      value={safeNullableText(
                        trailer.tipi,
                        trailerDetailText.fields.unspecified,
                      )}
                    />
                    <InfoCard
                      icon={Info}
                      label={trailerDetailText.fields.notes}
                      value={safeText(trailer.notlar)}
                    />
                  </div>
                </div>
              </div>
            )}

            {activeTab === "technical" && (
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                <div className="space-y-6">
                  <h3 className="px-1 text-xs font-bold uppercase tracking-widest text-secondary">
                    {trailerDetailText.sections.weight}
                  </h3>
                  <div className="grid grid-cols-1 gap-4">
                    <InfoCard
                      icon={Weight}
                      label={trailerDetailText.fields.emptyWeight}
                      value={safeMetric(trailer.bos_agirlik_kg, locale, "kg")}
                    />
                    <InfoCard
                      icon={CircleDot}
                      label={trailerDetailText.fields.tireCount}
                      value={safeMetric(trailer.lastik_sayisi, locale)}
                    />
                  </div>
                </div>
                <div className="space-y-6">
                  <h3 className="px-1 text-xs font-bold uppercase tracking-widest text-secondary">
                    {trailerDetailText.sections.physical}
                  </h3>
                  <div className="grid grid-cols-1 gap-4">
                    <InfoCard
                      icon={CircleDot}
                      label={trailerDetailText.fields.rollingResistance}
                      value={safeMetric(
                        trailer.dorse_lastik_direnc_katsayisi,
                        locale,
                      )}
                    />
                    <InfoCard
                      icon={CircleDot}
                      label={trailerDetailText.fields.dragContribution}
                      value={safeMetric(trailer.dorse_hava_direnci, locale)}
                    />
                  </div>
                </div>
              </div>
            )}

            {activeTab === "maintenance" && (
              <div className="flex flex-col items-center justify-center rounded-3xl border-2 border-border border-dashed bg-elevated/5 py-12 text-secondary">
                <Truck size={48} className="mb-4 opacity-20" />
                <p className="font-medium">
                  {trailerDetailText.maintenance.unavailableTitle}
                </p>
                <p className="text-sm">
                  {trailerDetailText.maintenance.unavailableDescription}
                </p>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-3 border-t border-border bg-elevated/20 p-6">
            <button
              onClick={onClose}
              className="rounded-xl border border-border px-6 py-2.5 font-medium text-secondary transition-all hover:bg-elevated"
            >
              {trailerDetailText.fields.close}
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default TrailerDetailModal;
