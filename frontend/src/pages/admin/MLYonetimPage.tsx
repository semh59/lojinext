import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, BrainCircuit, Play } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import { useNotify } from "@/context/NotificationContext";
import { adminMlApi } from "@/api/admin";
import { vehicleService } from "@/api/vehicles";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useAdminResources } from "@/resources/useResources";
import { useLocale } from "../../hooks/useLocale";
import { useTranslation } from "react-i18next";
import { getMlTaskStatusMeta } from "@/lib/status-labels";

export default function AdminModelManagementPage() {
  const { adminMlText } = useAdminResources();
  const { t, i18n } = useTranslation();
  const locale = useLocale();
  usePageTitle(t("admin.ml_models", "ML Models"));
  const queryClient = useQueryClient();
  const { notify } = useNotify();
  const [selectedVehicleId, setSelectedVehicleId] = useState<number | null>(
    null,
  );

  const { data: queue = [], isLoading } = useQuery({
    queryKey: ["mlQueue"],
    queryFn: () => adminMlApi.getQueue(50),
    refetchInterval: 10_000,
  });

  const { data: vehicleData } = useQuery({
    queryKey: ["mlVehicles"],
    queryFn: () => vehicleService.getAll({ aktif_only: true, limit: 100 }),
    staleTime: 10 * 60 * 1000,
  });

  const vehicles = useMemo(() => vehicleData?.items || [], [vehicleData]);

  useEffect(() => {
    if (selectedVehicleId === null && vehicles.length > 0) {
      setSelectedVehicleId(vehicles[0].id ?? null);
    }
  }, [selectedVehicleId, vehicles]);

  const triggerMutation = useMutation({
    mutationFn: (vehicleId: number) => adminMlApi.triggerTraining(vehicleId),
    onSuccess: () => {
      notify("success", adminMlText.notifications.trainingStarted);
      queryClient.invalidateQueries({ queryKey: ["mlQueue"] });
    },
    onError: (error: any) => {
      notify(
        "error",
        error?.response?.data?.error?.message ||
          error?.response?.data?.detail ||
          error.message ||
          adminMlText.notifications.trainingStartFailed,
      );
    },
  });

  // Real backend enum (EgitimKuyrugu.durum / MLTaskRead) is uppercase
  // (WAITING|RUNNING|COMPLETED|FAILED|CANCELED) — normalise before
  // comparing so real data (and any legacy lowercase caller) both match.
  const completedCount = queue.filter(
    (task) => task.durum?.toUpperCase() === "COMPLETED",
  ).length;
  const runningCount = queue.filter(
    (task) => task.durum?.toUpperCase() === "RUNNING",
  ).length;
  const latestRmse = queue.find(
    (task) => typeof task.metrics?.rmse === "number",
  )?.metrics?.rmse;

  const handleTrigger = () => {
    if (!selectedVehicleId) {
      notify("error", adminMlText.notifications.selectVehicle);
      return;
    }
    triggerMutation.mutate(selectedVehicleId);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-primary">
            {adminMlText.heading}
          </h1>
          <p className="mt-1 text-secondary">{adminMlText.description}</p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={selectedVehicleId ?? ""}
            onChange={(event) =>
              setSelectedVehicleId(Number(event.target.value) || null)
            }
            className="h-10 rounded-xl border border-border bg-elevated px-3 text-sm text-primary outline-none"
          >
            {vehicles.length === 0 ? (
              <option value="">{adminMlText.vehicleNotFound}</option>
            ) : (
              vehicles.map((vehicle) => (
                <option key={vehicle.id} value={vehicle.id}>
                  {vehicle.plaka} - {vehicle.marka} {vehicle.model}
                </option>
              ))
            )}
          </select>

          <Button
            variant="primary"
            className="flex items-center gap-2"
            onClick={handleTrigger}
            disabled={triggerMutation.isPending || !selectedVehicleId}
          >
            {triggerMutation.isPending ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-bg-base/20 border-t-bg-base" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            {adminMlText.startTraining}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <Card padding="md" className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-accent/10">
            <BrainCircuit className="h-6 w-6 text-accent" />
          </div>
          <div>
            <p className="text-sm font-bold uppercase tracking-widest text-secondary">
              {adminMlText.cards.totalTasks}
            </p>
            <p className="mt-0.5 text-2xl font-black text-primary">
              {queue.length}
            </p>
          </div>
        </Card>

        <Card padding="md" className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-warning/10">
            <Activity className="h-6 w-6 text-warning" />
          </div>
          <div>
            <p className="text-sm font-bold uppercase tracking-widest text-secondary">
              {adminMlText.cards.runningTasks}
            </p>
            <p className="mt-0.5 text-2xl font-black text-primary">
              {runningCount}
            </p>
          </div>
        </Card>

        <Card padding="md" className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-success/10">
            <Activity className="h-6 w-6 text-success" />
          </div>
          <div>
            <p className="text-sm font-bold uppercase tracking-widest text-secondary">
              {adminMlText.cards.latestRmse}
            </p>
            <p className="mt-0.5 text-2xl font-black text-primary">
              {typeof latestRmse === "number" ? latestRmse.toFixed(2) : "-"}
            </p>
            <p className="text-xs text-secondary">
              {adminMlText.cards.completedTasks(completedCount)}
            </p>
          </div>
        </Card>
      </div>

      <Card padding="none">
        <div className="border-b border-border bg-elevated/50 p-4">
          <h2 className="text-base font-bold text-primary">
            {adminMlText.table.title}
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
                <TableHead>{adminMlText.table.vehicleId}</TableHead>
                <TableHead>{adminMlText.table.status}</TableHead>
                <TableHead>{adminMlText.table.algorithmRmse}</TableHead>
                <TableHead>{adminMlText.table.duration}</TableHead>
                <TableHead>{adminMlText.table.detail}</TableHead>
                <TableHead>{adminMlText.table.createdAt}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {queue.map((task) => (
                <TableRow key={task.id}>
                  <TableCell className="font-medium">
                    {adminMlText.table.vehiclePrefix} #{task.arac_id}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        task.durum?.toUpperCase() === "COMPLETED"
                          ? "success"
                          : task.durum?.toUpperCase() === "FAILED"
                            ? "danger"
                            : task.durum?.toUpperCase() === "RUNNING"
                              ? "warning"
                              : "default"
                      }
                    >
                      {
                        getMlTaskStatusMeta(task.durum ?? "", i18n.language)
                          .label
                      }
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {task.metrics ? (
                      <span className="text-xs font-medium text-secondary">
                        {task.metrics.algorithm || "-"} /{" "}
                        {typeof task.metrics.rmse === "number"
                          ? task.metrics.rmse.toFixed(2)
                          : "-"}
                      </span>
                    ) : (
                      "-"
                    )}
                  </TableCell>
                  <TableCell className="text-sm">
                    {task.training_time_seconds
                      ? `${task.training_time_seconds.toFixed(1)} ${
                          adminMlText.table.secondsShort
                        }`
                      : "-"}
                  </TableCell>
                  <TableCell
                    className="max-w-xs truncate text-sm text-secondary"
                    title={task.error_message || task.trigger_reason || ""}
                  >
                    {task.error_message || task.trigger_reason || "-"}
                  </TableCell>
                  <TableCell className="text-xs text-secondary">
                    {(() => {
                      const createdAt = task.olusturma || task.created_at;
                      return createdAt
                        ? new Date(createdAt).toLocaleString(locale)
                        : "-";
                    })()}
                  </TableCell>
                </TableRow>
              ))}

              {queue.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="h-32 text-center text-secondary"
                  >
                    {adminMlText.table.empty}
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
