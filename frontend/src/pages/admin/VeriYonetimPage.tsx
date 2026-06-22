import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, RotateCcw } from "lucide-react";

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
import { adminImportsApi } from "@/api/admin";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useAdminResources } from "@/resources/useResources";
import { useLocale } from "../../hooks/useLocale";
import { useTranslation } from "react-i18next";

export default function AdminDataManagementPage() {
  const { adminDataManagementText } = useAdminResources();
  const { t } = useTranslation();
  const locale = useLocale();
  const mapImportStatus = (status?: string) => {
    switch (status) {
      case "tamamlandi":
        return {
          label: adminDataManagementText.statusLabels.completed,
          variant: "success" as const,
        };
      case "hata":
        return {
          label: adminDataManagementText.statusLabels.error,
          variant: "danger" as const,
        };
      case "geri_alindi":
        return {
          label: adminDataManagementText.statusLabels.rolledBack,
          variant: "warning" as const,
        };
      default:
        return {
          label: adminDataManagementText.statusLabels.default,
          variant: "default" as const,
        };
    }
  };
  usePageTitle(t("admin.data_management", "Data Management"));
  const qc = useQueryClient();
  const { notify } = useNotify();

  const { data: history = [], isLoading } = useQuery({
    queryKey: ["adminImportHistory"],
    queryFn: () => adminImportsApi.getHistory(50),
    staleTime: 2 * 60 * 1000,
  });

  const rollbackMutation = useMutation({
    mutationFn: adminImportsApi.rollback,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["adminImportHistory"] });
      notify(
        "success",
        adminDataManagementText.notifications.rollbackSuccessTitle,
        adminDataManagementText.notifications.rollbackSuccessMessage,
      );
    },
    onError: (err: Error) => {
      notify(
        "error",
        adminDataManagementText.notifications.rollbackFailedTitle,
        err.message ||
          adminDataManagementText.notifications.rollbackFailedFallback,
      );
    },
  });

  const handleRollback = (jobId: number) => {
    if (!window.confirm(adminDataManagementText.rollbackConfirm)) {
      return;
    }
    rollbackMutation.mutate(jobId);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-primary">
            {adminDataManagementText.heading}
          </h1>
          <p className="mt-1 text-secondary">
            {adminDataManagementText.description}
          </p>
        </div>
      </div>

      <Card padding="none">
        <div className="flex items-center gap-2 border-b border-border bg-elevated/50 p-4">
          <Database className="h-5 w-5 text-secondary" />
          <h2 className="text-base font-bold text-primary">
            {adminDataManagementText.sectionTitle}
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
                <TableHead>
                  {adminDataManagementText.headers.fileName}
                </TableHead>
                <TableHead>{adminDataManagementText.headers.type}</TableHead>
                <TableHead>
                  {adminDataManagementText.headers.createdAt}
                </TableHead>
                <TableHead>{adminDataManagementText.headers.status}</TableHead>
                <TableHead>{adminDataManagementText.headers.counts}</TableHead>
                <TableHead className="text-right">
                  {adminDataManagementText.headers.actions}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {history.map((job: any) => {
                const status = mapImportStatus(job.durum);

                return (
                  <TableRow key={job.id}>
                    <TableCell className="font-medium">
                      {job.dosya_adi}
                    </TableCell>
                    <TableCell className="text-xs font-bold uppercase text-secondary">
                      {job.aktarim_tipi}
                    </TableCell>
                    <TableCell className="text-sm">
                      {new Date(job.baslama_zamani).toLocaleString(locale)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={status.variant}>{status.label}</Badge>
                    </TableCell>
                    <TableCell className="text-sm">
                      <span className="font-medium text-success">
                        {job.basarili}
                      </span>{" "}
                      /{" "}
                      <span className="ml-1 font-medium text-danger">
                        {job.hatali}
                      </span>{" "}
                      /{" "}
                      <span className="ml-1 text-secondary">{job.toplam}</span>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 border-warning/20 text-warning hover:bg-warning/5 hover:text-warning/80"
                        onClick={() => handleRollback(job.id)}
                        disabled={
                          job.durum === "geri_alindi" ||
                          (rollbackMutation.isPending &&
                            rollbackMutation.variables === job.id)
                        }
                      >
                        {rollbackMutation.isPending &&
                        rollbackMutation.variables === job.id ? (
                          <div className="mr-2 h-3 w-3 animate-spin rounded-full border-2 border-warning/20 border-t-warning" />
                        ) : (
                          <RotateCcw className="mr-2 h-3 w-3" />
                        )}
                        {adminDataManagementText.rollbackAction}
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
              {history.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="h-32 text-center text-secondary"
                  >
                    {adminDataManagementText.empty}
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
