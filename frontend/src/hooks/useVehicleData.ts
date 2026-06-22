import { useEffect, useState } from "react";

import { zodResolver } from "@hookform/resolvers/zod";
import { SubmitHandler, useForm } from "react-hook-form";
import * as z from "zod";

import { Vehicle } from "../types";
import { useVehiclesResources } from "../resources/useResources";
const YAKIT_TIPLERI = ["DIZEL", "BENZIN", "LPG", "HYBRID", "ELEKTRIK"] as const;

export { YAKIT_TIPLERI };

const DEFAULT_PHYSICS = {
  bos_agirlik_kg: 8000,
  hava_direnc_katsayisi: 0.7,
  on_kesit_alani_m2: 8.5,
  motor_verimliligi: 0.38,
  lastik_direnc_katsayisi: 0.007,
  maks_yuk_kapasitesi_kg: 26000,
};

interface UseVehicleDataProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (vehicle: Partial<Vehicle>) => Promise<void>;
  vehicle?: Vehicle | null;
}

export function useVehicleData({
  isOpen,
  onClose,
  onSave,
  vehicle,
}: UseVehicleDataProps) {
  const { vehicleModalText } = useVehiclesResources();
  const vehicleSchema = z.object({
    plaka: z
      .string()
      .min(3, vehicleModalText.validation.plateMin)
      .transform((value) => value.replace(/\s+/g, "").toUpperCase()),
    marka: z.string().min(2, vehicleModalText.validation.brandMin).max(50),
    model: z.string().max(50).optional(),
    yil: z
      .number()
      .min(1990)
      .max(new Date().getFullYear() + 1),
    yakit_tipi: z.enum(YAKIT_TIPLERI).default("DIZEL"),
    tank_kapasitesi: z.number().min(1).max(5000),
    hedef_tuketim: z.number().min(1).max(100),
    dingil_sayisi: z.number().int().min(1).max(10).default(2),
    muayene_tarihi: z.string().optional().nullable(),
    sigorta_tarihi: z.string().optional().nullable(),
    motor_no: z.string().max(50).optional().nullable(),
    sasi_no: z.string().max(50).optional().nullable(),
    notlar: z.string().max(500).optional(),
    aktif: z.boolean(),
    bos_agirlik_kg: z.number().min(0),
    hava_direnc_katsayisi: z.number().min(0),
    on_kesit_alani_m2: z.number().min(0),
    motor_verimliligi: z.number().min(0).max(1),
    lastik_direnc_katsayisi: z.number().min(0),
    maks_yuk_kapasitesi_kg: z.number().min(0),
  });
  type VehicleFormData = z.infer<typeof vehicleSchema>;
  const [showAdvanced, setShowAdvanced] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<VehicleFormData>({
    resolver: zodResolver(vehicleSchema) as any,
    defaultValues: {
      plaka: "",
      marka: "",
      model: "",
      yil: new Date().getFullYear(),
      yakit_tipi: "DIZEL" as const,
      tank_kapasitesi: 600,
      hedef_tuketim: 32,
      dingil_sayisi: 2,
      muayene_tarihi: "",
      sigorta_tarihi: "",
      motor_no: "",
      sasi_no: "",
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

    if (vehicle) {
      reset({
        ...DEFAULT_PHYSICS,
        ...vehicle,
        yakit_tipi:
          (vehicle.yakit_tipi as (typeof YAKIT_TIPLERI)[number]) || "DIZEL",
        dingil_sayisi: (vehicle as any).dingil_sayisi ?? 2,
        muayene_tarihi: (vehicle as any).muayene_tarihi?.split("T")[0] ?? "",
      } as any);
    } else {
      reset({
        plaka: "",
        marka: "",
        model: "",
        yil: new Date().getFullYear(),
        yakit_tipi: "DIZEL",
        tank_kapasitesi: 600,
        hedef_tuketim: 32,
        dingil_sayisi: 2,
        muayene_tarihi: "",
        sigorta_tarihi: "",
        motor_no: "",
        sasi_no: "",
        notlar: "",
        aktif: true,
        ...DEFAULT_PHYSICS,
      });
    }
    setShowAdvanced(false);
  }, [vehicle, isOpen, reset]);

  const onSubmit: SubmitHandler<VehicleFormData> = async (data) => {
    try {
      await onSave(data);
      onClose();
    } catch (saveError) {
      console.error("Vehicle save error:", saveError);
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
