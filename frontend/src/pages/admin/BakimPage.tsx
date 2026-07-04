import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  CalendarDays,
  CheckCircle,
  AlertTriangle,
  List,
  Plus,
  ShieldCheck,
  Sparkles,
  Wrench,
} from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { RequirePermission } from "@/components/auth/RequirePermission";
import { adminMaintenanceApi, type BakimTipi } from "@/api/admin";
import { vehicleService } from "@/api/vehicles";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import { useNotify } from "@/context/NotificationContext";
import { usePageTitle } from "@/hooks/usePageTitle";
import { BreakdownReportModal } from "@/components/maintenance/BreakdownReportModal";
import { InspectionTab } from "@/components/admin/maintenance/InspectionTab";
import { MaintenanceCalendar } from "@/components/admin/maintenance/MaintenanceCalendar";
import { PredictionsTable } from "@/components/admin/maintenance/PredictionsTable";
import { cn } from "@/lib/utils";
import { useMaintenancePredictionsResources } from "@/resources/useResources";
import { useAdminResources } from "@/resources/useResources";
import { useLocale } from "../../hooks/useLocale";
import { useTranslation } from "react-i18next";

export default function AdminMaintenancePage() {
  const { adminMaintenanceText } = useAdminResources();
  const { t } = useTranslation();
  const locale = useLocale();
  // Backend contract (MaintenanceAlertItem, /admin/maintenance/alerts) sends
  // `vade_durumu: "OVERDUE" | "UPCOMING"` — NOT `durum: "gecikmis"/"yaklasiyor"`.
  // The previous switch matched a field/value shape that never existed on
  // the wire, so every alert silently fell through to the default badge.
  const mapMaintenanceStatus = (status?: string) => {
    switch (status) {
      case "OVERDUE":
        return {
          label: adminMaintenanceText.statusLabels.overdue,
          variant: "danger" as const,
        };
      case "UPCOMING":
        return {
          label: adminMaintenanceText.statusLabels.upcoming,
          variant: "warning" as const,
        };
      default:
        return {
          label: adminMaintenanceText.statusLabels.default,
          variant: "default" as const,
        };
    }
  };
  const { maintenancePredictionsText } = useMaintenancePredictionsResources();
  usePageTitle(t("admin.maintenance", "Maintenance"));
  const qc = useQueryClient();
  const { notify } = useNotify();

  const { data: alertsRaw = [], isLoading } = useQuery({
    queryKey: ["adminMaintenanceAlerts"],
    queryFn: () => adminMaintenanceApi.getAlerts(),
    staleTime: 2 * 60 * 1000,
  });
  const alerts = Array.isArray(alertsRaw) ? alertsRaw : [];

  const completeMutation = useMutation({
    mutationFn: adminMaintenanceApi.markComplete,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["adminMaintenanceAlerts"] });
      notify(
        "success",
        adminMaintenanceText.notifications.completeSuccessTitle,
        adminMaintenanceText.notifications.completeSuccessMessage,
      );
    },
    onError: (err: Error) => {
      notify(
        "error",
        adminMaintenanceText.notifications.actionFailedTitle,
        err.message || adminMaintenanceText.notifications.actionFailedFallback,
      );
    },
  });

  // ── Yeni bakım/arıza giriş formu ─────────────────────────────────
  const [isEntryOpen, setEntryOpen] = useState(false);
  const [entryForm, setEntryForm] = useState({
    arac_id: "",
    bakim_tipi: "PERIYODIK" as BakimTipi,
    km_bilgisi: "",
    bakim_tarihi: new Date().toISOString().slice(0, 10),
    maliyet: "",
    detaylar: "",
  });
  const [entryError, setEntryError] = useState<string | null>(null);
  const [breakdownOpen, setBreakdownOpen] = useState(false);

  const { data: vehiclesResp } = useQuery({
    queryKey: ["vehiclesForMaintenance"],
    queryFn: () => vehicleService.getAll({ limit: 500 }),
    enabled: isEntryOpen,
    staleTime: 5 * 60 * 1000,
  });
  const vehicles = vehiclesResp?.items ?? [];

  const createMutation = useMutation({
    mutationFn: () =>
      adminMaintenanceApi.create({
        arac_id: Number(entryForm.arac_id),
        bakim_tipi: entryForm.bakim_tipi,
        km_bilgisi: Number(entryForm.km_bilgisi),
        bakim_tarihi: new Date(entryForm.bakim_tarihi).toISOString(),
        maliyet: Number(entryForm.maliyet || 0),
        detaylar: entryForm.detaylar.trim(),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["adminMaintenanceAlerts"] });
      void qc.invalidateQueries({ queryKey: ["maintenancePredictions"] });
      notify(
        "success",
        t("admin.bakim_created", "Record created"),
        t(
          "admin.bakim_created_detail",
          "Maintenance/breakdown record successfully created.",
        ),
      );
      setEntryOpen(false);
    },
    onError: (err: unknown) => {
      const data = (
        err as {
          response?: {
            data?: { detail?: string; error?: { message?: string } };
          };
        }
      )?.response?.data;
      const detail =
        data?.error?.message ??
        data?.detail ??
        t("admin.bakim_create_failed", "Record could not be created.");
      setEntryError(detail);
    },
  });

  const openEntry = () => {
    setEntryForm({
      arac_id: "",
      bakim_tipi: "PERIYODIK",
      km_bilgisi: "",
      bakim_tarihi: new Date().toISOString().slice(0, 10),
      maliyet: "",
      detaylar: "",
    });
    setEntryError(null);
    setEntryOpen(true);
  };

  const submitEntry = () => {
    setEntryError(null);
    if (!entryForm.arac_id) {
      setEntryError(t("admin.bakim_vehicle_required", "Select vehicle"));
      return;
    }
    // KM, bakım/arıza takibi için zorunlu — boş bırakılıp 0 kaydedilmesi
    // aracın servis geçmişini bozar (sıfır km'lik servis kaydı anlamsız).
    if (!entryForm.km_bilgisi || Number(entryForm.km_bilgisi) <= 0) {
      setEntryError(
        t(
          "admin.bakim_km_required",
          "KM is required (for vehicle service tracking)",
        ),
      );
      return;
    }
    createMutation.mutate();
  };

  // URL state: ?view=calendar|predictions|history
  const [searchParams, setSearchParams] = useSearchParams();
  const viewParam = searchParams.get("view") ?? "history";
  const activeView: "history" | "predictions" | "calendar" | "muayene" =
    viewParam === "calendar"
      ? "calendar"
      : viewParam === "predictions"
        ? "predictions"
        : viewParam === "muayene"
          ? "muayene"
          : "history";

  const setView = (
    view: "history" | "predictions" | "calendar" | "muayene",
  ) => {
    const next = new URLSearchParams(searchParams);
    if (view === "history") {
      next.delete("view");
    } else {
      next.set("view", view);
    }
    setSearchParams(next, { replace: true });
  };

  const tabs: Array<{
    id: "history" | "predictions" | "calendar" | "muayene";
    label: string;
    icon: typeof List;
  }> = [
    {
      id: "history",
      label: maintenancePredictionsText.tabs.history,
      icon: List,
    },
    {
      id: "predictions",
      label: maintenancePredictionsText.tabs.list,
      icon: Sparkles,
    },
    {
      id: "calendar",
      label: maintenancePredictionsText.tabs.calendar,
      icon: CalendarDays,
    },
    {
      id: "muayene",
      label: maintenancePredictionsText.tabs.muayene,
      icon: ShieldCheck,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-primary">
            {adminMaintenanceText.heading}
          </h1>
          <p className="mt-1 text-secondary">
            {adminMaintenanceText.description}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Arıza Bildir — herkese açık (operatör/sürücü); izin gerektirmez */}
          <Button variant="danger" onClick={() => setBreakdownOpen(true)}>
            <AlertTriangle size={16} className="mr-2" />
            {t("admin.bakim_report_btn", "Arıza Bildir")}
          </Button>
          <RequirePermission permission="bakim_ekle">
            <Button variant="outline" onClick={openEntry}>
              <Plus size={16} className="mr-2" />
              {t("admin.bakim_add_btn", "New Maintenance / Breakdown")}
            </Button>
          </RequirePermission>
        </div>
      </div>

      {/* Tab switcher (D.3) */}
      <div className="flex gap-1 rounded-xl border border-border bg-surface p-1 w-fit">
        {tabs.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setView(t.id)}
              className={cn(
                "flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all",
                activeView === t.id
                  ? "bg-accent text-white shadow-sm"
                  : "text-secondary hover:text-primary",
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {t.label}
            </button>
          );
        })}
      </div>

      {activeView === "predictions" && <PredictionsTable />}
      {activeView === "calendar" && <MaintenanceCalendar />}
      {activeView === "muayene" && <InspectionTab />}

      {activeView === "history" && (
        <Card padding="none">
          <div className="flex items-center gap-2 border-b border-border bg-elevated/50 p-4">
            <Wrench className="h-5 w-5 text-secondary" />
            <h2 className="text-base font-bold text-primary">
              {adminMaintenanceText.sectionTitle}
            </h2>
          </div>
          {isLoading ? (
            <div className="flex h-48 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{adminMaintenanceText.headers.vehicle}</TableHead>
                  <TableHead>
                    {adminMaintenanceText.headers.maintenanceType}
                  </TableHead>
                  <TableHead>
                    {adminMaintenanceText.headers.plannedDateOrKm}
                  </TableHead>
                  <TableHead>{adminMaintenanceText.headers.status}</TableHead>
                  <TableHead className="text-right">
                    {adminMaintenanceText.headers.actions}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {alerts.map((alert: any) => {
                  const status = mapMaintenanceStatus(alert.vade_durumu);

                  return (
                    <TableRow key={alert.id}>
                      <TableCell className="font-medium">
                        {adminMaintenanceText.vehiclePrefix} #{alert.arac_id}
                      </TableCell>
                      <TableCell className="text-xs font-bold uppercase text-secondary">
                        {alert.bakim_tipi}
                      </TableCell>
                      <TableCell className="text-sm">
                        {alert.tarih
                          ? new Date(alert.tarih).toLocaleDateString(locale)
                          : "-"}
                        {alert.km_bilgisi ? ` / ${alert.km_bilgisi} KM` : ""}
                      </TableCell>
                      <TableCell>
                        <Badge variant={status.variant}>{status.label}</Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-8 border-success/20 text-success hover:bg-success/5 hover:text-success/80"
                          onClick={() => completeMutation.mutate(alert.id)}
                          disabled={completeMutation.isPending}
                        >
                          <CheckCircle className="mr-2 h-3 w-3" />
                          {adminMaintenanceText.completeAction}
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
                {alerts.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={5}
                      className="h-32 text-center text-secondary"
                    >
                      {adminMaintenanceText.empty}
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          )}
        </Card>
      )}

      <Modal
        isOpen={isEntryOpen}
        onClose={() => setEntryOpen(false)}
        title={t("admin.bakim_form_title", "New Maintenance / Breakdown Entry")}
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-secondary mb-1">
              {t("admin.bakim_vehicle_label", "Vehicle")}
            </label>
            <select
              value={entryForm.arac_id}
              onChange={(e) =>
                setEntryForm((f) => ({ ...f, arac_id: e.target.value }))
              }
              className="w-full bg-elevated border border-border rounded-card px-3 py-2 text-sm text-primary focus:outline-none focus:border-accent"
            >
              <option value="">
                {t("admin.bakim_select_vehicle", "Select vehicle…")}
              </option>
              {vehicles.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.plaka} {v.marka ? `— ${v.marka}` : ""}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-secondary mb-1">
                {t("admin.bakim_type_label", "Type")}
              </label>
              <select
                value={entryForm.bakim_tipi}
                onChange={(e) =>
                  setEntryForm((f) => ({
                    ...f,
                    bakim_tipi: e.target.value as BakimTipi,
                  }))
                }
                className="w-full bg-elevated border border-border rounded-card px-3 py-2 text-sm text-primary focus:outline-none focus:border-accent"
              >
                <option value="PERIYODIK">
                  {t("admin.bakim_type_periodic", "Periodic Maintenance")}
                </option>
                <option value="ARIZA">
                  {t("admin.bakim_type_breakdown", "Breakdown")}
                </option>
                <option value="ACIL">
                  {t("admin.bakim_acil_type", "Emergency")}
                </option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-secondary mb-1">
                {t("admin.bakim_date_label", "Date")}
              </label>
              <input
                type="date"
                value={entryForm.bakim_tarihi}
                onChange={(e) =>
                  setEntryForm((f) => ({ ...f, bakim_tarihi: e.target.value }))
                }
                className="w-full bg-elevated border border-border rounded-card px-3 py-2 text-sm text-primary focus:outline-none focus:border-accent"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-secondary mb-1">
                {t("admin.bakim_km_label", "KM")}{" "}
                <span className="text-red-500">*</span>
              </label>
              <input
                type="number"
                min={1}
                required
                value={entryForm.km_bilgisi}
                onChange={(e) =>
                  setEntryForm((f) => ({ ...f, km_bilgisi: e.target.value }))
                }
                placeholder={t(
                  "admin.bakim_km_placeholder",
                  "Vehicle's current km",
                )}
                className="w-full bg-elevated border border-border rounded-card px-3 py-2 text-sm text-primary focus:outline-none focus:border-accent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-secondary mb-1">
                {t("admin.bakim_cost_label", "Cost (TL)")}
              </label>
              <input
                type="number"
                value={entryForm.maliyet}
                onChange={(e) =>
                  setEntryForm((f) => ({ ...f, maliyet: e.target.value }))
                }
                className="w-full bg-elevated border border-border rounded-card px-3 py-2 text-sm text-primary focus:outline-none focus:border-accent"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-secondary mb-1">
              {t("admin.bakim_details_label", "Details")}
            </label>
            <textarea
              value={entryForm.detaylar}
              onChange={(e) =>
                setEntryForm((f) => ({ ...f, detaylar: e.target.value }))
              }
              rows={3}
              className="w-full bg-elevated border border-border rounded-card px-3 py-2 text-sm text-primary focus:outline-none focus:border-accent"
            />
          </div>

          {entryError && <p className="text-sm text-danger">{entryError}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setEntryOpen(false)}>
              {t("common.cancel", "Cancel")}
            </Button>
            <Button onClick={submitEntry} disabled={createMutation.isPending}>
              {createMutation.isPending
                ? t("common.saving", "Saving...")
                : t("common.save", "Save")}
            </Button>
          </div>
        </div>
      </Modal>

      <BreakdownReportModal
        isOpen={breakdownOpen}
        onClose={() => setBreakdownOpen(false)}
      />
    </div>
  );
}
