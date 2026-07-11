import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Pencil, Plus, Trash2 } from "lucide-react";
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
import { useTranslation } from "react-i18next";

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
  const { t } = useTranslation();
  usePageTitle(adminNotificationsText.heading);
  const qc = useQueryClient();
  const [isModalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<RuleForm>(EMPTY_RULE_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [editingRuleId, setEditingRuleId] = useState<number | null>(null);
  const [togglingRuleId, setTogglingRuleId] = useState<number | null>(null);

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
      toast.success(
        t("admin.bildirim_create_success", "Notification rule created"),
      );
      setModalOpen(false);
      setForm(EMPTY_RULE_FORM);
    },
    onError: (err: any) => {
      setFormError(
        err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          err.message,
      );
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      ruleId,
      body,
    }: {
      ruleId: number;
      body: {
        olay_tipi: string;
        kanallar: string[];
        alici_rol_id: number;
        aktif: boolean;
      };
    }) => adminNotificationsApi.updateRule(ruleId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["adminNotificationRules"] });
      toast.success(adminNotificationsText.notifications.updateSuccess);
      setModalOpen(false);
      setEditingRuleId(null);
      setForm(EMPTY_RULE_FORM);
    },
    onError: (err: any) => {
      setFormError(
        err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          adminNotificationsText.notifications.updateFailedFallback,
      );
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (ruleId: number) => adminNotificationsApi.deleteRule(ruleId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["adminNotificationRules"] });
      toast.success(adminNotificationsText.notifications.deleteSuccess);
    },
    onError: (err: any) => {
      toast.error(
        err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          adminNotificationsText.notifications.deleteFailedFallback,
      );
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ ruleId, aktif }: { ruleId: number; aktif: boolean }) =>
      adminNotificationsApi.updateRule(ruleId, { aktif }),
    onMutate: ({ ruleId }) => setTogglingRuleId(ruleId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["adminNotificationRules"] });
    },
    onError: (err: any) => {
      toast.error(
        err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          adminNotificationsText.notifications.updateFailedFallback,
      );
    },
    onSettled: () => setTogglingRuleId(null),
  });

  const openEditModal = (rule: {
    id: number;
    olay_tipi: string;
    kanallar: string[];
    alici_rol_id: number;
    aktif: boolean;
  }) => {
    setEditingRuleId(rule.id);
    setForm({
      olay_tipi: rule.olay_tipi,
      kanallar: rule.kanallar ?? [],
      alici_rol_id: String(rule.alici_rol_id),
      aktif: rule.aktif,
    });
    setFormError(null);
    setModalOpen(true);
  };

  const handleDelete = (ruleId: number) => {
    if (!window.confirm(adminNotificationsText.actions.deleteConfirm)) return;
    deleteMutation.mutate(ruleId);
  };

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
    if (!form.olay_tipi.trim())
      return setFormError(
        t("admin.bildirim_event_required", "Event type is required"),
      );
    if (form.kanallar.length === 0)
      return setFormError(
        t("admin.bildirim_channel_required", "Select at least one channel"),
      );
    if (!form.alici_rol_id)
      return setFormError(
        t("admin.bildirim_role_required", "Target role is required"),
      );
    const body = {
      olay_tipi: form.olay_tipi.trim(),
      kanallar: form.kanallar,
      alici_rol_id: Number(form.alici_rol_id),
      aktif: form.aktif,
    };
    if (editingRuleId != null) {
      updateMutation.mutate({ ruleId: editingRuleId, body });
    } else {
      createMutation.mutate(body);
    }
  };

  const isSubmitting = createMutation.isPending || updateMutation.isPending;

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
            setEditingRuleId(null);
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
                <TableHead className="text-right">
                  {adminNotificationsText.headers.actions}
                </TableHead>
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
                    <button
                      type="button"
                      role="switch"
                      aria-checked={rule.aktif}
                      aria-label={
                        rule.aktif
                          ? adminNotificationsText.statuses.active
                          : adminNotificationsText.statuses.passive
                      }
                      disabled={togglingRuleId === rule.id}
                      onClick={() =>
                        toggleMutation.mutate({
                          ruleId: rule.id,
                          aktif: !rule.aktif,
                        })
                      }
                      className="disabled:opacity-50"
                    >
                      <Badge variant={rule.aktif ? "success" : "default"}>
                        {rule.aktif
                          ? adminNotificationsText.statuses.active
                          : adminNotificationsText.statuses.passive}
                      </Badge>
                    </button>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center justify-end gap-1">
                      <button
                        type="button"
                        title={adminNotificationsText.actions.edit}
                        onClick={() => openEditModal(rule)}
                        className="rounded-lg p-1.5 text-secondary transition-colors hover:bg-elevated hover:text-accent"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        title={adminNotificationsText.actions.delete}
                        onClick={() => handleDelete(rule.id)}
                        className="rounded-lg p-1.5 text-secondary transition-colors hover:bg-danger/10 hover:text-danger"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {rules.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={6}
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
        onClose={() => {
          setModalOpen(false);
          setEditingRuleId(null);
        }}
        title={
          editingRuleId != null
            ? adminNotificationsText.editTitle
            : t("admin.bildirim_form_title", "New Notification Rule")
        }
        size="md"
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label={t("admin.bildirim_event_type_label", "Event Type")}
            type="text"
            placeholder={t(
              "admin.bildirim_event_placeholder",
              "e.g. FUEL_ANOMALY, TRIP_DELAY",
            )}
            value={form.olay_tipi}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, olay_tipi: e.target.value }))
            }
          />

          <div className="flex flex-col gap-2">
            <label className="text-[13px] font-medium text-primary">
              {t("admin.bildirim_channels_label", "Channels")}
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
              {t("admin.bildirim_target_role_label", "Target Role")}
            </label>
            <select
              value={form.alici_rol_id}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, alici_rol_id: e.target.value }))
              }
              className="flex h-10 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-primary outline-none focus:border-accent focus:ring-2 focus:ring-accent/5"
            >
              <option value="">
                {t("admin.bildirim_select_role", "Select role...")}
              </option>
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
              {form.aktif
                ? t("admin.bildirim_rule_active", "Rule Active")
                : t("admin.bildirim_rule_passive", "Rule Inactive")}
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
              onClick={() => {
                setModalOpen(false);
                setEditingRuleId(null);
              }}
              disabled={isSubmitting}
            >
              {t("common.cancel", "Cancel")}
            </Button>
            <Button type="submit" variant="primary" disabled={isSubmitting}>
              {isSubmitting
                ? editingRuleId != null
                  ? t("common.saving", "Saving...")
                  : t("admin.bildirim_creating", "Creating...")
                : editingRuleId != null
                  ? t("common.save", "Save")
                  : t("common.create", "Create")}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
