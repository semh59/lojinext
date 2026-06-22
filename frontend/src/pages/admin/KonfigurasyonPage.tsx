import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Save, Settings } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { useNotify } from "@/context/NotificationContext";
import { cn } from "@/lib/utils";
import { adminApi } from "@/api/admin";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useAdminResources } from "@/resources/useResources";

interface ConfigItem {
  anahtar: string;
  deger: unknown;
  tip: string;
  birim?: string;
  min_deger?: number;
  max_deger?: number;
  grup: string;
  aciklama?: string;
  yeniden_baslat: boolean;
}

const adminUpdateReason = "Updated from admin panel";

export default function AdminConfigurationPage() {
  const { adminConfigurationText } = useAdminResources();
  usePageTitle("Konfigürasyon");
  const qc = useQueryClient();
  const { notify } = useNotify();
  const [localValues, setLocalValues] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState<string | null>(null);

  const { data: configs = [], isLoading } = useQuery<ConfigItem[]>({
    queryKey: ["adminConfigs"],
    queryFn: () => adminApi.getConfigs(),
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (configs.length > 0) {
      const initialValues: Record<string, unknown> = {};
      configs.forEach((config) => {
        initialValues[config.anahtar] = config.deger;
      });
      setLocalValues(initialValues);
    }
  }, [configs]);

  const updateMutation = useMutation({
    mutationFn: ({ key, value }: { key: string; value: unknown }) =>
      adminApi.updateConfig(key, value, adminUpdateReason),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["adminConfigs"] });
      notify(
        "success",
        adminConfigurationText.notifications.saveSuccessTitle,
        adminConfigurationText.notifications.saveSuccessMessage,
      );
    },
    onError: (err: any) => {
      const message =
        err.response?.data?.detail ||
        adminConfigurationText.notifications.saveFailedFallback;
      notify(
        "error",
        adminConfigurationText.notifications.saveFailedTitle,
        message,
      );
    },
    onSettled: () => {
      setSaving(null);
    },
  });

  const handleSave = (key: string) => {
    setSaving(key);
    updateMutation.mutate({ key, value: localValues[key] });
  };

  const handleChange = (key: string, value: unknown) => {
    setLocalValues((current) => ({ ...current, [key]: value }));
  };

  if (isLoading) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-4">
        <div className="h-10 w-10 animate-spin rounded-full border-[3px] border-accent/10 border-t-accent" />
        <p className="animate-pulse text-xs font-bold uppercase tracking-widest text-tertiary">
          {adminConfigurationText.loading}
        </p>
      </div>
    );
  }

  const groupedConfigs = configs.reduce(
    (groups, config) => {
      if (!groups[config.grup]) groups[config.grup] = [];
      groups[config.grup].push(config);
      return groups;
    },
    {} as Record<string, ConfigItem[]>,
  );

  return (
    <div className="max-w-5xl space-y-8">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold text-primary">
          {adminConfigurationText.heading}
        </h1>
        <p className="text-sm text-secondary">
          {adminConfigurationText.description}
        </p>
      </div>

      {Object.entries(groupedConfigs).map(([group, items]) => (
        <div key={group} className="space-y-4">
          <div className="flex items-center gap-2 px-1">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/5 text-accent">
              <Settings size={16} />
            </div>
            <h2 className="text-sm font-bold uppercase tracking-[0.1em] text-primary">
              {`${group.replace("_", " ")} ${
                adminConfigurationText.groupSuffix
              }`}
            </h2>
          </div>

          <Card
            padding="none"
            className="overflow-hidden border-border/50 glass"
          >
            <div className="divide-y divide-border/30">
              {items.map((config) => (
                <div
                  key={config.anahtar}
                  className="group grid grid-cols-1 gap-6 p-6 transition-colors hover:bg-elevated md:grid-cols-12"
                >
                  <div className="space-y-2 md:col-span-5">
                    <div className="flex items-center gap-2">
                      <label className="text-sm font-bold text-primary transition-colors group-hover:text-accent">
                        {config.anahtar}
                      </label>
                      {config.yeniden_baslat ? (
                        <div className="flex items-center gap-1.5 rounded-full border border-warning/10 bg-warning/5 px-2 py-0.5 text-warning">
                          <RotateCcw className="h-3 w-3" />
                          <span className="text-[9px] font-black uppercase tracking-tighter">
                            {adminConfigurationText.reloadRequired}
                          </span>
                        </div>
                      ) : null}
                    </div>
                    {config.aciklama ? (
                      <p className="max-w-sm text-xs leading-relaxed text-tertiary">
                        {config.aciklama}
                      </p>
                    ) : null}
                  </div>

                  <div className="flex items-center gap-4 md:col-span-7">
                    <div className="relative flex-1">
                      <Input
                        type={
                          config.tip === "int" || config.tip === "float"
                            ? "number"
                            : "text"
                        }
                        value={String(localValues[config.anahtar] ?? "")}
                        onChange={(event) => {
                          const rawValue = event.target.value;
                          handleChange(
                            config.anahtar,
                            config.tip === "int"
                              ? parseInt(rawValue, 10)
                              : config.tip === "float"
                                ? parseFloat(rawValue)
                                : rawValue,
                          );
                        }}
                        className="h-11 w-full rounded-xl border-border/50 bg-elevated/30 focus:border-accent/40"
                        placeholder={adminConfigurationText.valuePlaceholder}
                      />
                      {config.birim ? (
                        <span className="absolute right-4 top-1/2 -translate-y-1/2 rounded-md border border-border/50 bg-elevated/80 px-2 py-1 text-[10px] font-black uppercase tracking-widest text-tertiary">
                          {config.birim}
                        </span>
                      ) : null}
                    </div>

                    <Button
                      variant="primary"
                      onClick={() => handleSave(config.anahtar)}
                      disabled={
                        saving === config.anahtar ||
                        localValues[config.anahtar] === config.deger
                      }
                      className={cn(
                        "h-11 rounded-xl px-6 text-xs font-bold uppercase tracking-widest transition-all",
                        localValues[config.anahtar] === config.deger
                          ? "opacity-50 grayscale"
                          : "shadow-md shadow-accent/20",
                      )}
                    >
                      {saving === config.anahtar ? (
                        <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white" />
                      ) : (
                        <>
                          <Save className="mr-2 h-4 w-4" />
                          {adminConfigurationText.actions.save}
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      ))}
    </div>
  );
}
