import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Key, Lock, Save } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { useNotify } from "@/context/NotificationContext";
import { cn } from "@/lib/utils";
import { adminIntegrationsApi, type AdminIntegrationStatus } from "@/api/admin";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useAdminResources } from "@/resources/useResources";
import { useTranslation } from "react-i18next";

export default function EntegrasyonlarPage() {
  const { adminIntegrationsText } = useAdminResources();
  const { t } = useTranslation();
  usePageTitle(t("admin.integrations", "Integrations"));
  const qc = useQueryClient();
  const { notify } = useNotify();
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);

  const { data: statuses = [], isLoading } = useQuery<AdminIntegrationStatus[]>(
    {
      queryKey: ["adminIntegrationStatuses"],
      queryFn: () => adminIntegrationsApi.getStatuses(),
      staleTime: 60 * 1000,
    },
  );

  const updateMutation = useMutation({
    mutationFn: ({
      servisAdi,
      apiKey,
    }: {
      servisAdi: string;
      apiKey: string;
    }) => adminIntegrationsApi.updateKey(servisAdi, apiKey),
    onSuccess: (_, variables) => {
      void qc.invalidateQueries({ queryKey: ["adminIntegrationStatuses"] });
      setDrafts((current) => ({ ...current, [variables.servisAdi]: "" }));
      notify(
        "success",
        adminIntegrationsText.notifications.saveSuccessTitle,
        adminIntegrationsText.notifications.saveSuccessMessage,
      );
    },
    onError: (err: any) => {
      const message =
        err.response?.data?.error?.message ||
        err.response?.data?.detail ||
        adminIntegrationsText.notifications.saveFailedFallback;
      notify(
        "error",
        adminIntegrationsText.notifications.saveFailedTitle,
        message,
      );
    },
    onSettled: () => {
      setSaving(null);
    },
  });

  const handleSave = (servisAdi: string) => {
    const value = (drafts[servisAdi] ?? "").trim();
    if (!value) {
      notify(
        "error",
        adminIntegrationsText.notifications.saveFailedTitle,
        adminIntegrationsText.notifications.emptyValue,
      );
      return;
    }
    setSaving(servisAdi);
    updateMutation.mutate({ servisAdi, apiKey: value });
  };

  if (isLoading) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-4">
        <div className="h-10 w-10 animate-spin rounded-full border-[3px] border-accent/10 border-t-accent" />
        <p className="animate-pulse text-xs font-bold uppercase tracking-widest text-tertiary">
          {adminIntegrationsText.loading}
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl space-y-8">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold text-primary">
          {adminIntegrationsText.heading}
        </h1>
        <p className="text-sm text-secondary">
          {adminIntegrationsText.description}
        </p>
      </div>

      <div className="flex items-start gap-3 rounded-xl border border-warning/10 bg-warning/5 p-4 text-warning">
        <Lock className="mt-0.5 h-4 w-4 shrink-0" />
        <p className="text-xs leading-relaxed">
          {adminIntegrationsText.writeOnlyNotice}
        </p>
      </div>

      <Card padding="none" className="overflow-hidden border-border/50 glass">
        <div className="divide-y divide-border/30">
          {statuses.map((status) => {
            const serviceLabel =
              adminIntegrationsText.serviceNames[
                status.servis_adi as keyof typeof adminIntegrationsText.serviceNames
              ] ?? status.servis_adi;
            const draftValue = drafts[status.servis_adi] ?? "";
            const canSave = draftValue.trim().length > 0;

            return (
              <div
                key={status.servis_adi}
                className="group grid grid-cols-1 gap-6 p-6 transition-colors hover:bg-elevated md:grid-cols-12"
              >
                <div className="space-y-2 md:col-span-5">
                  <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/5 text-accent">
                      <Key size={16} />
                    </div>
                    <label className="text-sm font-bold text-primary transition-colors group-hover:text-accent">
                      {serviceLabel}
                    </label>
                  </div>
                  <div className="flex items-center gap-2 pl-10">
                    <span
                      className={cn(
                        "rounded-full border px-2 py-0.5 text-[9px] font-black uppercase tracking-tighter",
                        status.configured
                          ? "border-success/10 bg-success/5 text-success"
                          : "border-border/50 bg-elevated/50 text-tertiary",
                      )}
                    >
                      {status.configured
                        ? adminIntegrationsText.statusLabels.configured
                        : adminIntegrationsText.statusLabels.notConfigured}
                    </span>
                    <span className="text-[11px] text-tertiary">
                      {status.guncellenme_tarihi
                        ? adminIntegrationsText.lastUpdated(
                            new Date(
                              status.guncellenme_tarihi,
                            ).toLocaleString(),
                          )
                        : adminIntegrationsText.neverUpdated}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-4 md:col-span-7">
                  <Input
                    type="password"
                    autoComplete="off"
                    value={draftValue}
                    onChange={(event) =>
                      setDrafts((current) => ({
                        ...current,
                        [status.servis_adi]: event.target.value,
                      }))
                    }
                    className="h-11 flex-1 rounded-xl border-border/50 bg-elevated/30 focus:border-accent/40"
                    placeholder={adminIntegrationsText.inputPlaceholder}
                  />

                  <Button
                    variant="primary"
                    onClick={() => handleSave(status.servis_adi)}
                    disabled={saving === status.servis_adi || !canSave}
                    className={cn(
                      "h-11 rounded-xl px-6 text-xs font-bold uppercase tracking-widest transition-all",
                      !canSave
                        ? "opacity-50 grayscale"
                        : "shadow-md shadow-accent/20",
                    )}
                  >
                    {saving === status.servis_adi ? (
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white" />
                    ) : (
                      <>
                        <Save className="mr-2 h-4 w-4" />
                        {adminIntegrationsText.actions.save}
                      </>
                    )}
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
