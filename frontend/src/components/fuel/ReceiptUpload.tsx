import { useState } from "react";
import { useTranslation } from "react-i18next";
import { fuelService, type OcrPreview } from "../../api/fuel";

type ParsedFields = OcrPreview["yapilandirilmis"];

interface Props {
  onConfirm: (fields: ParsedFields) => void;
}

export function ReceiptUpload({ onConfirm }: Props) {
  const { t } = useTranslation();
  const [fields, setFields] = useState<ParsedFields | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const FIELD_LABELS: Record<keyof ParsedFields, string> = {
    istasyon: t("fuel.receipt_field"),
    litre: t("fuel.litres"),
    tutar: t("fuel.total"),
    km: "Km",
    tarih: t("common.date"),
  };

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fuelService.ocrPreview(file);
      setFields(res.yapilandirilmis);
    } catch {
      setError(t("fuel.ocr_error"));
      setFields({
        litre: null,
        tutar: null,
        km: null,
        tarih: null,
        istasyon: null,
      });
    } finally {
      setLoading(false);
    }
  };

  const set = (k: keyof ParsedFields, v: string) =>
    setFields((f) => (f ? { ...f, [k]: v } : f));

  return (
    <div className="rounded-modal border border-border bg-surface p-4 space-y-3">
      <h3 className="text-sm font-semibold text-secondary">
        {t("fuel.receipt_label")}
      </h3>
      <label className="block text-sm text-tertiary">
        <span className="sr-only">{t("fuel.receipt_label")}</span>
        <input
          type="file"
          accept="image/*"
          aria-label={t("fuel.receipt_label")}
          onChange={onFile}
          className="mt-1 block"
        />
      </label>
      {loading && (
        <p className="text-sm text-tertiary">{t("common.loading")}</p>
      )}
      {error && <p className="text-sm text-warning">{error}</p>}
      {fields && (
        <div className="space-y-2">
          {(Object.keys(FIELD_LABELS) as (keyof ParsedFields)[]).map((k) => (
            <label
              key={k}
              className="flex items-center justify-between gap-2 text-sm"
            >
              <span className="text-tertiary">{FIELD_LABELS[k]}</span>
              <input
                value={fields[k] ?? ""}
                onChange={(e) => set(k, e.target.value)}
                className="rounded-card border border-border bg-elevated px-2 py-1"
              />
            </label>
          ))}
          <button
            type="button"
            onClick={() => fields && onConfirm(fields)}
            className="rounded-card bg-elevated px-3 py-1 text-sm text-primary"
          >
            {t("common.confirm")}
          </button>
        </div>
      )}
    </div>
  );
}

export default ReceiptUpload;
