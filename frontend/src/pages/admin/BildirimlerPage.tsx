import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Plus } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import { cn } from "@/lib/utils";
import { adminNotificationsApi, adminRolesApi } from "@/api/admin";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useAdminResources } from "@/resources/useResources";

const CHANNELS = ["EMAIL", "PUSH", "TELEGRAM", "SMS"] as const;

interface RuleForm {
  olay_tipi: string;
  kanallar: string[];
  alici_rol_id: string;
  aktif: boolean;
}

const EMPTY_RULE_FORM: RuleForm = {
  olay_tipi: "",
  kanallar: [],
  alici_rol_id: "",
  aktif: true,
};

export default function AdminNotificationsPage() {
  const { adminNotificationsText } = useAdminResources();
  usePageTitle(adminNotificationsText.heading);
  const qc = useQueryClient();
  const [isModalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<RuleForm>(EMPTY_RULE_FORM);
  const [formError, setFormError] = useState<string | null>(null);

  const { data: rules = [], isLoading } = useQuery({
    queryKey: ["adminNotificationRules"],
    queryFn: () => adminNotificationsApi.getRules(),
    staleTime: 2 * 60 * 1000,
  });

  const { data: roles = [] } = useQuery({
    queryKey: ["adminRoles"],
    queryFn: () => adminRolesApi.getAll(),
    staleTime: 10 * 60 * 1000,
  });

  const createMutation = useMutation({
    mutationFn: adminNotificationsApi.createRule,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["adminNotificationRules"] });
      toast.success("Bildirim kuralı oluşturuldu");
      setModalOpen(false);
      setForm(EMPTY_RULE_FORM);
    },
    onError: (err: Error) => {
      setFormError(err.message);
    },
  });

  const toggleChannel = (ch: string) => {
    setForm((prev) => ({
      ...prev,
      kanallar: prev.kanallar.includes(ch)
        ? prev.kanallar.filter((c) => c !== ch)
        : [...prev.kanallar, ch],
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!form.olay_tipi.trim()) return setFormError("Olay tipi zorunludur");
    if (form.kanallar.length === 0)
      return setFormError("En az bir kanal seçin");
    if (!form.alici_rol_id) return setFormError("Hedef rol zorunludur");
    createMutation.mutate({
      olay_tipi: form.olay_tipi.trim(),
      kanallar: form.kanallar,
      alici_rol_id: Number(form.alici_rol_id),
      aktif: form.aktif,
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-primary">
            {adminNotificationsText.heading}
          </h1>
          <p className="mt-1 text-secondary">
            {adminNotificationsText.description}
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => {
            setForm(EMPTY_RULE_FORM);
            setFormError(null);
            setModalOpen(true);
          }}
          className="flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          {adminNotificationsText.addRule}
        </Button>
      </div>

      <Card padding="none">
        <div className="flex items-center justify-between border-b border-border bg-elevated/50 p-4">
          <div className="flex items-center gap-2">
            <Bell className="h-5 w-5 text-secondary" />
            <h2 className="text-base font-bold text-primary">
              {adminNotificationsText.sectionTitle}
            </h2>
          </div>
        </div>
        {isLoading ? (
          <div className="flex h-48 items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-accent border-t-transparent" />
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>
                  {adminNotificationsText.headers.eventType}
                </TableHead>
                <TableHead>{adminNotificationsText.headers.channels}</TableHead>
                <TableHead>
                  {adminNotificationsText.headers.targetRole}
                </TableHead>
                <TableHead>{adminNotificationsText.headers.template}</TableHead>
                <TableHead>{adminNotificationsText.headers.status}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules.map((rule: any) => (
                <TableRow key={rule.id}>
                  <TableCell className="font-medium text-accent">
                    {rule.olay_tipi}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {rule.kanallar?.map((channel: string) => (
                        <Badge
                          key={channel}
                          variant="default"
                          className="text-[10px] uppercase"
                        >
                          {channel}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell>
                    {adminNotificationsText.rolePrefix} #{rule.alici_rol_id}
                  </TableCell>
                  <TableCell className="max-w-xs truncate text-secondary">
                    {rule.sablon_icerik || "-"}
                  </TableCell>
                  <TableCell>
                    <Badge variant={rule.aktif ? "success" : "default"}>
                      {rule.aktif
                        ? adminNotificationsText.statuses.active
                        : adminNotificationsText.statuses.passive}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
              {rules.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="h-32 text-center text-secondary"
                  >
                    {adminNotificationsText.empty}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
      </Card>

      <Modal
        isOpen={isModalOpen}
        onClose={() => setModalOpen(false)}
        title="Yeni Bildirim Kuralı"
        size="md"
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Olay Tipi"
            type="text"
            placeholder="örn. FUEL_ANOMALY, TRIP_DELAY"
            value={form.olay_tipi}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, olay_tipi: e.target.value }))
            }
          />

          <div className="flex flex-col gap-2">
            <label className="text-[13px] font-medium text-primary">
              Kanallar
            </label>
            <div className="flex flex-wrap gap-2">
              {CHANNELS.map((ch) => (
                <button
                  key={ch}
                  type="button"
                  onClick={() => toggleChannel(ch)}
                  className={cn(
                    "rounded-lg border px-3 py-1.5 text-xs font-bold uppercase tracking-wide transition-all",
                    form.kanallar.includes(ch)
                      ? "border-accent bg-accent/10 text-accent"
                      : "border-border bg-surface text-secondary hover:border-accent/50",
                  )}
                >
                  {ch}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[13px] font-medium text-primary">
              Hedef Rol
            </label>
            <select
              value={form.alici_rol_id}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, alici_rol_id: e.target.value }))
              }
              className="flex h-10 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-primary outline-none focus:border-accent focus:ring-2 focus:ring-accent/5"
            >
              <option value="">Rol seçin...</option>
              {roles.map((r: any) => (
                <option key={r.id} value={String(r.id)}>
                  {r.ad}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              role="switch"
              aria-checked={form.aktif}
              onClick={() =>
                setForm((prev) => ({ ...prev, aktif: !prev.aktif }))
              }
              className={cn(
                "relative h-6 w-11 rounded-full transition-colors duration-200",
                form.aktif ? "bg-accent" : "bg-border",
              )}
            >
              <span
                className={cn(
                  "absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-200",
                  form.aktif ? "translate-x-5" : "translate-x-0",
                )}
              />
            </button>
            <span className="text-sm font-medium text-primary">
              {form.aktif ? "Kural Aktif" : "Kural Pasif"}
            </span>
          </div>

          {formError && (
            <p className="rounded-lg bg-danger/5 px-4 py-2.5 text-sm font-medium text-danger">
              {formError}
            </p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setModalOpen(false)}
              disabled={createMutation.isPending}
            >
              İptal
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={createMutation.isPending}
            >
              {createMutation.isPending ? "Oluşturuluyor..." : "Oluştur"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
