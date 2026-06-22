import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Shuffle } from "lucide-react";
import { toast } from "sonner";

import ErrorBoundary from "@/components/common/ErrorBoundary";
import { RequirePermission } from "@/components/auth/RequirePermission";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { adminAttributionApi } from "@/api/admin";
import { vehicleService } from "@/api/vehicles";
import { driverService } from "@/api/drivers";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useTranslation } from "react-i18next";

export default function AtamaPage() {
  const { t } = useTranslation();
  usePageTitle(t("admin.trip_assignment", "Trip Assignment"));

  const [seferId, setSeferId] = useState("");
  const [aracId, setAracId] = useState("");
  const [soforId, setSoforId] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: vehiclesResp } = useQuery({
    queryKey: ["vehiclesForAttribution"],
    queryFn: () => vehicleService.getAll({ limit: 500 }),
    staleTime: 5 * 60 * 1000,
  });
  const vehicles = vehiclesResp?.items ?? [];

  const { data: driversResp } = useQuery({
    queryKey: ["driversForAttribution"],
    queryFn: () => driverService.getAll({ limit: 500 }),
    staleTime: 5 * 60 * 1000,
  });
  const drivers = driversResp?.items ?? [];

  const overrideMutation = useMutation({
    mutationFn: () =>
      adminAttributionApi.override({
        sefer_id: Number(seferId),
        new_arac_id: aracId ? Number(aracId) : null,
        new_sofor_id: soforId ? Number(soforId) : null,
        reason: reason.trim(),
      }),
    onSuccess: () => {
      toast.success(t("admin.assignment_success"));
      setSeferId("");
      setAracId("");
      setSoforId("");
      setReason("");
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? t("admin.assignment_error");
      setError(detail);
    },
  });

  const submit = () => {
    setError(null);
    if (!seferId || Number(seferId) <= 0) {
      setError(t("admin.assignment_trip_invalid"));
      return;
    }
    if (!aracId && !soforId) {
      setError(t("admin.assignment_fields_required"));
      return;
    }
    if (reason.trim().length < 5) {
      setError(t("admin.assignment_reason_min"));
      return;
    }
    overrideMutation.mutate();
  };

  return (
    <ErrorBoundary>
      <div className="space-y-6 max-w-2xl">
        <div className="flex items-center gap-3">
          <Shuffle className="text-accent" size={24} />
          <div>
            <h1 className="text-xl font-bold text-primary">
              {t("admin.assignment_title")}
            </h1>
            <p className="text-sm text-secondary">
              {t("admin.assignment_subtitle")}
            </p>
          </div>
        </div>

        <Card className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-secondary mb-1">
              Trip ID
            </label>
            <input
              type="number"
              value={seferId}
              onChange={(e) => setSeferId(e.target.value)}
              placeholder={t("admin.assignment_trip_placeholder")}
              className="w-full bg-elevated border border-border rounded-card px-3 py-2 text-sm text-primary focus:outline-none focus:border-accent"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-secondary mb-1">
                {t("admin.assignment_vehicle_label")}
              </label>
              <select
                value={aracId}
                onChange={(e) => setAracId(e.target.value)}
                className="w-full bg-elevated border border-border rounded-card px-3 py-2 text-sm text-primary focus:outline-none focus:border-accent"
              >
                <option value="">{t("admin.assignment_no_change")}</option>
                {vehicles.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.plaka} {v.marka ? `— ${v.marka}` : ""}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-secondary mb-1">
                {t("admin.assignment_driver_label")}
              </label>
              <select
                value={soforId}
                onChange={(e) => setSoforId(e.target.value)}
                className="w-full bg-elevated border border-border rounded-card px-3 py-2 text-sm text-primary focus:outline-none focus:border-accent"
              >
                <option value="">{t("admin.assignment_no_change")}</option>
                {drivers.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.ad_soyad}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-secondary mb-1">
              {t("admin.assignment_reason_label")}
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              placeholder={t("admin.assignment_reason_placeholder")}
              className="w-full bg-elevated border border-border rounded-card px-3 py-2 text-sm text-primary focus:outline-none focus:border-accent"
            />
          </div>

          {error && <p className="text-sm text-danger">{error}</p>}

          <div className="flex justify-end">
            <RequirePermission
              permission="attribution_duzenle"
              fallback={
                <p className="text-sm text-tertiary">
                  {t("admin.assignment_no_permission")}
                </p>
              }
            >
              <Button onClick={submit} disabled={overrideMutation.isPending}>
                {overrideMutation.isPending
                  ? t("common.applying")
                  : t("admin.assignment_submit")}
              </Button>
            </RequirePermission>
          </div>
        </Card>
      </div>
    </ErrorBoundary>
  );
}
