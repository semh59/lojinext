import { useEffect, useState } from "react";

import { zodResolver } from "@hookform/resolvers/zod";
import { SubmitHandler, useForm } from "react-hook-form";
import * as z from "zod";

import { Dorse } from "../types";
import { useTrailersResources } from "../resources/useResources";

const DORSE_TIPLERI = [
  "Standart",
  "Frigo",
  "Tenteli",
  "Damperli",
  "Lowbed",
] as const;

export { DORSE_TIPLERI };

const DEFAULT_PHYSICS = {
  bos_agirlik_kg: 6000,
  maks_yuk_kapasitesi_kg: 24000,
  lastik_sayisi: 6,
  dorse_lastik_direnc_katsayisi: 0.006,
  dorse_hava_direnci: 0.2,
};

interface UseTrailerDataProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: Partial<Dorse>) => Promise<void>;
  trailer: Dorse | null;
}

export function useTrailerData({
  isOpen,
  onClose,
  onSave,
  trailer,
}: UseTrailerDataProps) {
  const { trailerModalText } = useTrailersResources();
  // Backend DorseBase (app/schemas/dorse.py) ile birebir — alanların
  // min/max/pattern sınırları oradaki Field(...) kısıtlarını yansıtır,
  // böylece geçersiz bir değer sunucuya hiç gitmeden (satır-içi hata ile)
  // engellenir (2026-07-09 tasarım denetimi bulgusu: eskiden bu form hiçbir
  // istemci-tarafı doğrulama yapmıyordu).
  const trailerSchema = z.object({
    plaka: z
      .string()
      .min(3, trailerModalText.validation.plateMin)
      .max(20)
      .transform((value) => value.replace(/\s+/g, "").toUpperCase()),
    marka: z.string().max(50).optional().nullable(),
    tipi: z.enum(DORSE_TIPLERI).default("Standart"),
    yil: z
      .number()
      .min(1990, trailerModalText.validation.yearMin)
      .max(new Date().getFullYear() + 1, trailerModalText.validation.yearMax)
      .optional()
      .nullable(),
    muayene_tarihi: z.string().optional().nullable(),
    bos_agirlik_kg: z
      .number()
      .gt(0, trailerModalText.validation.positive)
      .max(20000, trailerModalText.validation.emptyWeightMax),
    maks_yuk_kapasitesi_kg: z
      .number()
      .int()
      .gt(0, trailerModalText.validation.positive)
      .max(40000, trailerModalText.validation.payloadMax),
    lastik_sayisi: z
      .number()
      .int()
      .min(4, trailerModalText.validation.tireCountRange)
      .max(16, trailerModalText.validation.tireCountRange),
    dorse_lastik_direnc_katsayisi: z
      .number()
      .gt(0.001, trailerModalText.validation.positive)
      .max(0.1, trailerModalText.validation.rollingResistanceMax),
    dorse_hava_direnci: z
      .number()
      .gt(0, trailerModalText.validation.positive)
      .max(1.0, trailerModalText.validation.dragContributionMax),
    notlar: z.string().max(500).optional().nullable(),
    aktif: z.boolean(),
  });
  type TrailerFormData = z.infer<typeof trailerSchema>;
  const [showAdvanced, setShowAdvanced] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<TrailerFormData>({
    resolver: zodResolver(trailerSchema) as any,
    defaultValues: {
      plaka: "",
      marka: "",
      tipi: "Standart" as const,
      yil: new Date().getFullYear(),
      muayene_tarihi: "",
      notlar: "",
      aktif: true,
      ...DEFAULT_PHYSICS,
    },
  });

  const notes = watch("notlar") || "";

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    if (trailer) {
      reset({
        ...DEFAULT_PHYSICS,
        ...trailer,
        tipi: (trailer.tipi as (typeof DORSE_TIPLERI)[number]) || "Standart",
        muayene_tarihi: trailer.muayene_tarihi?.split("T")[0] ?? "",
      } as any);
    } else {
      reset({
        plaka: "",
        marka: "",
        tipi: "Standart",
        yil: new Date().getFullYear(),
        muayene_tarihi: "",
        notlar: "",
        aktif: true,
        ...DEFAULT_PHYSICS,
      });
    }
    setShowAdvanced(false);
  }, [trailer, isOpen, reset]);

  const onSubmit: SubmitHandler<TrailerFormData> = async (data) => {
    try {
      // Empty date input -> omit it (backend Optional[date] rejects "").
      const payload: Partial<TrailerFormData> = { ...data };
      if (!payload.muayene_tarihi) delete payload.muayene_tarihi;
      await onSave(payload as Partial<Dorse>);
      onClose();
    } catch (saveError) {
      console.error("Trailer save error:", saveError);
    }
  };

  return {
    showAdvanced,
    setShowAdvanced,
    register,
    handleSubmit,
    errors,
    isSubmitting,
    notes,
    onSubmit,
  };
}
