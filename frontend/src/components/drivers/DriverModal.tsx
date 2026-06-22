import { useEffect, useState } from "react";

import { zodResolver } from "@hookform/resolvers/zod";
import { AnimatePresence, motion } from "framer-motion";
import {
  Calendar,
  FileText,
  MessageCircle,
  Phone,
  Send,
  Shield,
  User,
  X,
} from "lucide-react";
import { Controller, SubmitHandler, useForm } from "react-hook-form";
import * as z from "zod";

import { Driver } from "../../types";
import {
  driverFilterText,
  driverModalText,
  driverModuleText,
} from "../../resources/tr/drivers";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";

const driverSchema = z.object({
  ad_soyad: z
    .string()
    .min(3, driverModalText.validation.nameMin)
    .max(100, driverModalText.validation.nameMax),
  telefon: z
    .string()
    .optional()
    .refine(
      (value) => !value || /^[0-9\s]{10,14}$/.test(value),
      driverModalText.validation.phone,
    ),
  ise_baslama: z.string().optional(),
  ehliyet_sinifi: z.string().min(1, driverModalText.validation.licenseClass),
  manual_score: z.number().min(0.1).max(2.0),
  notlar: z.string().max(500, driverModalText.validation.notesMax).optional(),
  aktif: z.boolean(),
  tc_no: z.string().max(11).optional().nullable(),
  dogum_tarihi: z.string().optional().nullable(),
  kan_grubu: z
    .enum(["A+", "A-", "B+", "B-", "AB+", "AB-", "0+", "0-", ""])
    .optional()
    .nullable(),
  telegram_id: z
    .string()
    .max(50)
    .regex(/^\d*$/, "Telegram ID yalnızca rakamlardan oluşmalıdır")
    .optional()
    .nullable(),
});

type DriverFormData = z.infer<typeof driverSchema>;
type TabId = "temel" | "kisisel" | "telegram";

interface DriverModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (driver: Partial<Driver>) => Promise<void>;
  driver?: Driver | null;
}

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  {
    id: "temel",
    label: "Temel Bilgiler",
    icon: <User className="h-3.5 w-3.5" />,
  },
  { id: "kisisel", label: "Kişisel", icon: <Shield className="h-3.5 w-3.5" /> },
  { id: "telegram", label: "Telegram", icon: <Send className="h-3.5 w-3.5" /> },
];

export function DriverModal({
  isOpen,
  onClose,
  onSave,
  driver,
}: DriverModalProps) {
  const [activeTab, setActiveTab] = useState<TabId>("temel");

  const {
    register,
    handleSubmit,
    control,
    reset,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<DriverFormData>({
    resolver: zodResolver(driverSchema),
    defaultValues: {
      ad_soyad: "",
      telefon: "",
      ise_baslama: new Date().toISOString().split("T")[0],
      ehliyet_sinifi: "E",
      manual_score: 1.0,
      notlar: "",
      aktif: true,
      tc_no: "",
      dogum_tarihi: "",
      kan_grubu: "",
      telegram_id: "",
    },
  });

  const notes = watch("notlar") || "";
  const manualScore = watch("manual_score");
  const telegramId = watch("telegram_id");

  useEffect(() => {
    if (!isOpen) return;
    setActiveTab("temel");

    if (driver) {
      reset({
        ad_soyad: driver.ad_soyad || "",
        telefon: driver.telefon || "",
        ise_baslama: driver.ise_baslama?.split("T")[0] || "",
        ehliyet_sinifi: driver.ehliyet_sinifi || "E",
        manual_score: driver.manual_score || 1.0,
        notlar: driver.notlar || "",
        aktif: driver.aktif ?? true,
        tc_no: driver.tc_no || "",
        dogum_tarihi: driver.dogum_tarihi?.split("T")[0] || "",
        kan_grubu:
          (driver.kan_grubu as
            | "A+"
            | "A-"
            | "B+"
            | "B-"
            | "AB+"
            | "AB-"
            | "0+"
            | "0-"
            | ""
            | null) || "",
        telegram_id: driver.telegram_id || "",
      });
    } else {
      reset({
        ad_soyad: "",
        telefon: "",
        ise_baslama: new Date().toISOString().split("T")[0],
        ehliyet_sinifi: "E",
        manual_score: 1.0,
        notlar: "",
        aktif: true,
        tc_no: "",
        dogum_tarihi: "",
        kan_grubu: "",
        telegram_id: "",
      });
    }
  }, [driver, isOpen, reset]);

  const onSubmit: SubmitHandler<DriverFormData> = async (data) => {
    try {
      await onSave({
        ...data,
        telefon: data.telefon?.replace(/\s/g, ""),
      });
      onClose();
    } catch (saveError) {
      console.error("Driver save error:", saveError);
    }
  };

  const formatPhone = (value: string): string => {
    const digits = value.replace(/\D/g, "").slice(0, 11);
    if (digits.length <= 4) return digits;
    if (digits.length <= 7) return `${digits.slice(0, 4)} ${digits.slice(4)}`;
    if (digits.length <= 9)
      return `${digits.slice(0, 4)} ${digits.slice(4, 7)} ${digits.slice(7)}`;
    return `${digits.slice(0, 4)} ${digits.slice(4, 7)} ${digits.slice(
      7,
      9,
    )} ${digits.slice(9)}`;
  };

  if (!isOpen) return null;

  const hasTemelError = !!(
    errors.ad_soyad ||
    errors.telefon ||
    errors.ehliyet_sinifi ||
    errors.ise_baslama ||
    errors.manual_score ||
    errors.notlar
  );
  const hasKisiselError = !!(
    errors.tc_no ||
    errors.dogum_tarihi ||
    errors.kan_grubu
  );
  const hasTelegramError = !!errors.telegram_id;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="flex w-full max-w-lg flex-col overflow-hidden rounded-[14px] border border-border bg-surface shadow-2xl"
        >
          {/* Header */}
          <div className="flex shrink-0 items-center justify-between border-b border-border bg-elevated/40 px-6 py-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-[10px] border border-border bg-surface text-accent shadow-sm">
                <User className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-base font-bold tracking-tight text-primary">
                  {driver
                    ? driverModalText.title.edit
                    : driverModalText.title.create}
                </h2>
                <p className="text-[11px] text-secondary">
                  {driverModalText.description}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="rounded-lg p-2 text-secondary transition-colors hover:bg-elevated hover:text-primary"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Tabs */}
          <div className="flex shrink-0 gap-1 border-b border-border bg-elevated/20 px-4 pt-3">
            {TABS.map((tab) => {
              const hasError =
                (tab.id === "temel" && hasTemelError) ||
                (tab.id === "kisisel" && hasKisiselError) ||
                (tab.id === "telegram" && hasTelegramError);
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-1.5 rounded-t-lg border-b-2 px-4 py-2.5 text-[11px] font-bold uppercase tracking-wider transition-all ${
                    activeTab === tab.id
                      ? "border-accent text-accent"
                      : "border-transparent text-secondary hover:text-primary"
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                  {hasError && (
                    <span className="ml-1 h-1.5 w-1.5 rounded-full bg-danger" />
                  )}
                </button>
              );
            })}
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit(onSubmit)}>
            <div className="max-h-[60vh] overflow-y-auto p-6">
              {/* Tab: Temel Bilgiler */}
              {activeTab === "temel" && (
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-secondary">
                      <User className="h-3.5 w-3.5" />
                      {driverModalText.fields.fullName}
                    </label>
                    <Input
                      {...register("ad_soyad")}
                      placeholder={driverModalText.placeholders.fullName}
                      className="border-transparent bg-elevated/50 text-primary focus:border-border"
                      error={!!errors.ad_soyad}
                    />
                    {errors.ad_soyad && (
                      <p className="text-[10px] font-bold uppercase tracking-tight text-danger">
                        {errors.ad_soyad.message}
                      </p>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-secondary">
                        <Phone className="h-3.5 w-3.5" />
                        {driverModalText.fields.phone}
                      </label>
                      <Controller
                        name="telefon"
                        control={control}
                        render={({ field }) => (
                          <Input
                            {...field}
                            onChange={(e) =>
                              field.onChange(formatPhone(e.target.value))
                            }
                            placeholder={driverModalText.placeholders.phone}
                            className="border-transparent bg-elevated/50 text-primary focus:border-border"
                            error={!!errors.telefon}
                          />
                        )}
                      />
                      {errors.telefon && (
                        <p className="text-[10px] font-bold uppercase tracking-tight text-danger">
                          {errors.telefon.message}
                        </p>
                      )}
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-[11px] font-bold uppercase tracking-widest text-secondary">
                        {driverModalText.fields.licenseClass}
                      </label>
                      <select
                        {...register("ehliyet_sinifi")}
                        className="h-10 w-full rounded-[8px] border border-border bg-elevated px-3 text-xs font-bold text-primary outline-none transition-all focus:border-secondary"
                      >
                        {driverModuleText.licenseOptions
                          .filter((v) => v)
                          .map((v) => (
                            <option key={v} value={v}>
                              {driverFilterText.licenseSuffix(v)}
                            </option>
                          ))}
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-secondary">
                        <Calendar className="h-3.5 w-3.5" />
                        {driverModalText.fields.startDate}
                      </label>
                      <Input
                        type="date"
                        {...register("ise_baslama")}
                        className="border-transparent bg-elevated/50 text-primary focus:border-border"
                        error={!!errors.ise_baslama}
                      />
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-[11px] font-bold uppercase tracking-widest text-secondary">
                        {driverModalText.fields.manualScore}:{" "}
                        <span className="text-accent">
                          {manualScore?.toFixed(1)}
                        </span>
                      </label>
                      <input
                        type="range"
                        min="0.1"
                        max="2.0"
                        step="0.1"
                        {...register("manual_score", { valueAsNumber: true })}
                        className="mt-2 h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-elevated accent-accent"
                      />
                      <div className="flex justify-between text-[10px] font-bold text-secondary">
                        <span>{driverModalText.scoreRange.low}</span>
                        <span>{driverModalText.scoreRange.high}</span>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-secondary">
                      <FileText className="h-3.5 w-3.5" />
                      {driverModalText.fields.notes}{" "}
                      <span className="font-medium text-secondary/50">
                        ({notes.length}/500)
                      </span>
                    </label>
                    <textarea
                      {...register("notlar")}
                      placeholder={driverModalText.placeholders.notes}
                      rows={3}
                      className={`w-full resize-none rounded-[8px] border bg-elevated px-4 py-3 text-xs text-primary outline-none transition-all ${
                        errors.notlar ? "border-danger" : "border-transparent"
                      }`}
                    />
                    {errors.notlar && (
                      <p className="text-[10px] font-bold uppercase tracking-tight text-danger">
                        {errors.notlar.message}
                      </p>
                    )}
                  </div>

                  <label className="flex cursor-pointer items-center gap-3 rounded-[8px] border border-border bg-elevated/30 p-3 transition-colors hover:bg-elevated/50">
                    <input
                      type="checkbox"
                      {...register("aktif")}
                      className="h-4 w-4 rounded border-border bg-surface text-accent focus:ring-accent"
                    />
                    <div>
                      <span className="text-xs font-bold text-primary">
                        {driverModalText.fields.active}
                      </span>
                      <p className="text-[10px] font-medium text-secondary">
                        {driverModalText.fields.activeDescription}
                      </p>
                    </div>
                  </label>
                </div>
              )}

              {/* Tab: Kişisel */}
              {activeTab === "kisisel" && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-[11px] font-bold uppercase tracking-widest text-secondary">
                        TC Kimlik No
                        <span className="ml-1 font-normal normal-case tracking-normal text-secondary/60">
                          (isteğe bağlı)
                        </span>
                      </label>
                      <Input
                        {...register("tc_no")}
                        placeholder="11 haneli TC kimlik numarası"
                        maxLength={11}
                        className="border-transparent bg-elevated/50 text-primary focus:border-border"
                        error={!!errors.tc_no}
                      />
                      {errors.tc_no && (
                        <p className="text-[10px] font-bold uppercase tracking-tight text-danger">
                          {errors.tc_no.message}
                        </p>
                      )}
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-[11px] font-bold uppercase tracking-widest text-secondary">
                        Kan Grubu
                        <span className="ml-1 font-normal normal-case tracking-normal text-secondary/60">
                          (isteğe bağlı)
                        </span>
                      </label>
                      <select
                        {...register("kan_grubu")}
                        className="h-10 w-full rounded-[8px] border border-border bg-elevated px-3 text-xs font-bold text-primary outline-none transition-all focus:border-secondary"
                      >
                        <option value="">Seçiniz</option>
                        {["A+", "A-", "B+", "B-", "AB+", "AB-", "0+", "0-"].map(
                          (kg) => (
                            <option key={kg} value={kg}>
                              {kg}
                            </option>
                          ),
                        )}
                      </select>
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-secondary">
                      <Calendar className="h-3.5 w-3.5" />
                      Doğum Tarihi
                      <span className="font-normal normal-case tracking-normal text-secondary/60">
                        (isteğe bağlı)
                      </span>
                    </label>
                    <Input
                      type="date"
                      {...register("dogum_tarihi")}
                      className="border-transparent bg-elevated/50 text-primary focus:border-border"
                      error={!!errors.dogum_tarihi}
                    />
                  </div>
                </div>
              )}

              {/* Tab: Telegram */}
              {activeTab === "telegram" && (
                <div className="space-y-5">
                  <div className="flex items-start gap-3 rounded-[10px] border border-info/20 bg-info/5 p-4">
                    <MessageCircle className="mt-0.5 h-4 w-4 shrink-0 text-info" />
                    <div className="text-xs text-secondary">
                      <p className="font-semibold text-primary">
                        Telegram botu nasıl kullanılır?
                      </p>
                      <ol className="mt-2 space-y-1 text-secondary">
                        <li>
                          1. Şoför Telegram'da{" "}
                          <span className="font-bold text-primary">
                            @userinfobot
                          </span>
                          'a yaz
                        </li>
                        <li>
                          2. Bot'tan gelen{" "}
                          <span className="font-bold text-primary">
                            numeric ID'yi
                          </span>{" "}
                          buraya gir
                        </li>
                        <li>3. Şoför artık belge fotoğrafı gönderebilir</li>
                      </ol>
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-secondary">
                      <Send className="h-3.5 w-3.5" />
                      Telegram Kullanıcı ID
                      <span className="font-normal normal-case tracking-normal text-secondary/60">
                        (isteğe bağlı)
                      </span>
                    </label>
                    <Input
                      {...register("telegram_id")}
                      placeholder="Örn: 123456789"
                      className="border-transparent bg-elevated/50 text-primary focus:border-border"
                      error={!!errors.telegram_id}
                    />
                    {errors.telegram_id && (
                      <p className="text-[10px] font-bold uppercase tracking-tight text-danger">
                        {errors.telegram_id.message}
                      </p>
                    )}
                    {telegramId && !errors.telegram_id && (
                      <div className="flex items-center gap-1.5 text-[10px] font-medium text-success">
                        <span className="h-1.5 w-1.5 rounded-full bg-success" />
                        Telegram ID tanımlandı
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex gap-3 border-t border-border px-6 py-4">
              <Button
                type="button"
                variant="secondary"
                className="h-10 flex-1 text-xs font-bold"
                onClick={onClose}
              >
                {driverModalText.actions.cancel}
              </Button>
              <Button
                type="submit"
                variant="primary"
                className="h-10 flex-1 text-xs font-bold"
                isLoading={isSubmitting}
              >
                {driver
                  ? driverModalText.actions.update
                  : driverModalText.actions.save}
              </Button>
            </div>
          </form>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
