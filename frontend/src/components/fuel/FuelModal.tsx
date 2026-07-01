import { useEffect } from "react";
import { useForm, SubmitHandler } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import * as z from "zod";

import { Input } from "../ui/Input";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { vehicleService } from "../../api/vehicles";
import { FuelRecord } from "../../types";
import { useFuelResources } from "../../resources/useResources";

interface FuelModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: Partial<FuelRecord>) => Promise<void>;
  record?: FuelRecord | null;
  /** Faz 6 — yeni kayıt modunda OCR'dan gelen ön-doldurma değerleri. */
  ocrPrefill?: Record<string, unknown> | null;
}

export function FuelModal({
  isOpen,
  onClose,
  onSave,
  record,
  ocrPrefill,
}: FuelModalProps) {
  const { fuelModalText } = useFuelResources();
  const fuelSchema = z.object({
    tarih: z.string().min(1, fuelModalText.validation.dateRequired),
    arac_id: z.number().min(1, fuelModalText.validation.vehicleRequired),
    istasyon: z.string().min(1, fuelModalText.validation.stationRequired),
    litre: z.number().min(0.1, fuelModalText.validation.litersPositive),
    fiyat_tl: z.number().min(0.1, fuelModalText.validation.unitPricePositive),
    toplam_tutar: z.number().min(0, fuelModalText.validation.totalPositive),
    km_sayac: z.number().min(0, fuelModalText.validation.odometerPositive),
    depo_durumu: z.enum([
      fuelModalText.enums.full,
      fuelModalText.enums.partial,
    ]),
    durum: z.enum([
      fuelModalText.enums.pending,
      fuelModalText.enums.approved,
      fuelModalText.enums.rejected,
    ]),
    fis_no: z.string().optional(),
  });
  type FuelFormData = z.infer<typeof fuelSchema>;
  const { data: vehiclesData = [] } = useQuery({
    queryKey: ["vehicles", { aktif_only: true }],
    queryFn: () => vehicleService.getAll({ limit: 100, aktif_only: true }),
    enabled: isOpen,
  });
  const vehicles = (
    Array.isArray(vehiclesData)
      ? vehiclesData
      : (vehiclesData as any).items || []
  ) as import("../../types").Vehicle[];

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FuelFormData>({
    resolver: zodResolver(fuelSchema),
    defaultValues: {
      tarih: new Date().toISOString().slice(0, 10),
      litre: 0,
      fiyat_tl: 0,
      toplam_tutar: 0,
      km_sayac: 0,
      depo_durumu: fuelModalText.enums.partial,
      durum: fuelModalText.enums.pending,
      istasyon: "",
    },
  });

  const liters = watch("litre");
  const unitPrice = watch("fiyat_tl");

  useEffect(() => {
    const total = (liters || 0) * (unitPrice || 0);
    setValue("toplam_tutar", Number.parseFloat(total.toFixed(2)));
  }, [liters, unitPrice, setValue]);

  useEffect(() => {
    if (!isOpen) return;

    if (record) {
      reset({
        ...record,
        tarih: record.tarih.slice(0, 10),
        fiyat_tl: record.birim_fiyat || record.fiyat_tl || 0,
        durum: record.durum || fuelModalText.enums.pending,
      } as any);
      return;
    }

    reset({
      tarih: new Date().toISOString().slice(0, 10),
      litre: 0,
      fiyat_tl: 0,
      toplam_tutar: 0,
      km_sayac: 0,
      depo_durumu: fuelModalText.enums.partial,
      durum: fuelModalText.enums.pending,
      istasyon: "",
      // Faz 6 — OCR önizlemesinden gelen değerler defaults üzerine yazılır.
      ...(ocrPrefill ?? {}),
    } as any);
  }, [
    isOpen,
    record,
    ocrPrefill,
    reset,
    fuelModalText.enums.partial,
    fuelModalText.enums.pending,
  ]);

  const onSubmit: SubmitHandler<FuelFormData> = async (data) => {
    try {
      await onSave(data as Partial<FuelRecord>);
      onClose();
    } catch (error) {
      console.error("Fuel save error:", error);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={record ? fuelModalText.editTitle : fuelModalText.createTitle}
    >
      <p className="mb-6 text-sm text-secondary">{fuelModalText.description}</p>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-xs font-bold text-secondary">
              {fuelModalText.labels.date}
            </label>
            <Input type="date" {...register("tarih")} error={!!errors.tarih} />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-bold text-secondary">
              {fuelModalText.labels.vehicle}
            </label>
            <select
              {...register("arac_id", { valueAsNumber: true })}
              className={`w-full h-10 px-3 rounded-md border ${
                errors.arac_id
                  ? "border-danger focus:ring-danger/20"
                  : "border-border focus:ring-accent/20"
              } bg-elevated text-primary text-sm focus:ring-2 outline-none transition-all`}
            >
              <option value="">{fuelModalText.placeholders.vehicle}</option>
              {vehicles.map((vehicle) => (
                <option key={vehicle.id} value={vehicle.id}>
                  {vehicle.plaka} — {vehicle.marka}
                </option>
              ))}
            </select>
            {errors.arac_id ? (
              <p className="mt-1 text-xs font-medium text-danger">
                {errors.arac_id.message}
              </p>
            ) : null}
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-bold text-secondary">
            {fuelModalText.labels.station}
          </label>
          <Input
            {...register("istasyon")}
            placeholder={fuelModalText.placeholders.station}
            error={!!errors.istasyon}
          />
          {errors.istasyon ? (
            <p className="text-xs font-medium text-danger">
              {errors.istasyon.message}
            </p>
          ) : null}
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-2">
            <label className="text-xs font-bold text-secondary">
              {fuelModalText.labels.liters}
            </label>
            <Input
              type="number"
              step="0.01"
              {...register("litre", { valueAsNumber: true })}
              error={!!errors.litre}
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-bold text-secondary">
              {fuelModalText.labels.unitPrice}
            </label>
            <Input
              type="number"
              step="0.01"
              {...register("fiyat_tl", { valueAsNumber: true })}
              error={!!errors.fiyat_tl}
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-bold text-secondary">
              {fuelModalText.labels.total}
            </label>
            <Input
              type="number"
              {...register("toplam_tutar", { valueAsNumber: true })}
              readOnly
              className="bg-elevated font-bold text-primary"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-xs font-bold text-secondary">
              {fuelModalText.labels.odometer}
            </label>
            <Input
              type="number"
              {...register("km_sayac", { valueAsNumber: true })}
              error={!!errors.km_sayac}
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-bold text-secondary">
              {fuelModalText.labels.receiptNumber}
            </label>
            <Input
              {...register("fis_no")}
              placeholder={fuelModalText.placeholders.receiptNumber}
              error={!!errors.fis_no}
            />
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-bold text-secondary">
            {fuelModalText.labels.tankStatus}
          </label>
          <select
            {...register("depo_durumu")}
            className="w-full h-10 rounded-md border border-border bg-elevated px-3 text-sm text-primary outline-none transition-all focus:ring-2 focus:ring-accent/20"
          >
            <option value={fuelModalText.enums.full}>
              {fuelModalText.tankStatusOptions.full}
            </option>
            <option value={fuelModalText.enums.partial}>
              {fuelModalText.tankStatusOptions.partial}
            </option>
            <option value={fuelModalText.tankStatusOptions.unknown}>
              {fuelModalText.tankStatusOptions.unknown}
            </option>
          </select>
        </div>

        <div className="flex gap-4 pt-4">
          <Button
            type="button"
            variant="secondary"
            className="flex-1 h-10"
            onClick={onClose}
          >
            {fuelModalText.actions.cancel}
          </Button>
          <Button
            type="submit"
            variant="primary"
            className="flex-1 h-10"
            isLoading={isSubmitting}
          >
            {fuelModalText.actions.save}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
