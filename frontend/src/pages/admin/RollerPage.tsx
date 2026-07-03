import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Shield, ShieldPlus, Check, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";

import ErrorBoundary from "@/components/common/ErrorBoundary";
import { RequirePermission } from "@/components/auth/RequirePermission";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import { AdminRoleRecord, KNOWN_PERMISSIONS, adminRolesApi } from "@/api/admin";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useTranslation } from "react-i18next";

// Sistem rolleri — backend de düzenleme/silmeyi reddeder; UI'da aksiyon gizlenir.
const PROTECTED_ROLES = ["super_admin", "admin"];

type ModalMode = "create" | "edit";

export default function RollerPage() {
  const { t } = useTranslation();
  usePageTitle(t("admin.roles", "Roles"));
  const qc = useQueryClient();

  const { data: roles = [], isLoading } = useQuery({
    queryKey: ["adminRoles"],
    queryFn: () => adminRolesApi.getAll(),
    staleTime: 10 * 60 * 1000,
  });

  const [isModalOpen, setModalOpen] = useState(false);
  const [mode, setMode] = useState<ModalMode>("create");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [ad, setAd] = useState("");
  const [perms, setPerms] = useState<Record<string, boolean>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminRoleRecord | null>(
    null,
  );

  const saveMutation = useMutation({
    mutationFn: () => {
      const body = {
        ad: ad.trim(),
        yetkiler: Object.fromEntries(
          Object.entries(perms).filter(([, v]) => v),
        ),
      };
      return mode === "edit" && editingId != null
        ? adminRolesApi.update(editingId, body)
        : adminRolesApi.create(body);
    },
    onSuccess: () => {
      toast.success(
        mode === "edit" ? t("admin.role_updated") : t("admin.role_created"),
      );
      qc.invalidateQueries({ queryKey: ["adminRoles"] });
      setModalOpen(false);
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
        data?.error?.message ?? data?.detail ?? t("admin.operation_failed");
      setFormError(detail);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (roleId: number) => adminRolesApi.remove(roleId),
    onSuccess: () => {
      toast.success(t("admin.role_deleted"));
      qc.invalidateQueries({ queryKey: ["adminRoles"] });
      setDeleteTarget(null);
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
        data?.error?.message ?? data?.detail ?? t("admin.role_delete_failed");
      toast.error(detail);
      setDeleteTarget(null);
    },
  });

  const openCreate = () => {
    setMode("create");
    setEditingId(null);
    setAd("");
    setPerms({});
    setFormError(null);
    setModalOpen(true);
  };

  const openEdit = (role: AdminRoleRecord) => {
    setMode("edit");
    setEditingId(role.id);
    setAd(role.ad);
    setPerms({ ...(role.yetkiler || {}) });
    setFormError(null);
    setModalOpen(true);
  };

  const togglePerm = (key: string) =>
    setPerms((p) => ({ ...p, [key]: !p[key] }));

  const handleSubmit = () => {
    setFormError(null);
    if (ad.trim().length < 2) {
      setFormError(t("admin.role_name_min"));
      return;
    }
    if (!Object.values(perms).some(Boolean)) {
      setFormError(t("admin.role_permission_required"));
      return;
    }
    saveMutation.mutate();
  };

  return (
    <ErrorBoundary>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Shield className="text-accent" size={24} />
            <div>
              <h1 className="text-xl font-bold text-primary">
                {t("admin.roles")}
              </h1>
              <p className="text-sm text-secondary">
                {t("admin.roles_subtitle")}
              </p>
            </div>
          </div>
          <RequirePermission permission="rol_yaz">
            <Button onClick={openCreate}>
              <ShieldPlus size={16} className="mr-2" /> {t("admin.role_new")}
            </Button>
          </RequirePermission>
        </div>

        <Card className="p-0 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("admin.role_col_name")}</TableHead>
                <TableHead>{t("admin.role_col_count")}</TableHead>
                <TableHead>{t("admin.role_col_permissions")}</TableHead>
                <TableHead className="text-right">
                  {t("common.actions")}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-secondary">
                    {t("common.loading")}
                  </TableCell>
                </TableRow>
              ) : roles.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-secondary">
                    {t("admin.role_empty")}
                  </TableCell>
                </TableRow>
              ) : (
                roles.map((role: AdminRoleRecord) => {
                  const keys = Object.entries(role.yetkiler || {})
                    .filter(([, v]) => v)
                    .map(([k]) => k);
                  const isProtected = PROTECTED_ROLES.includes(role.ad);
                  return (
                    <TableRow key={role.id}>
                      <TableCell className="font-semibold text-primary">
                        {role.ad}
                        {isProtected && (
                          <Badge variant="info" className="ml-2">
                            {t("admin.role_system")}
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        {keys.includes("*")
                          ? t("admin.role_all_perms")
                          : keys.length}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {keys.slice(0, 8).map((k) => (
                            <Badge key={k} variant="default">
                              {k}
                            </Badge>
                          ))}
                          {keys.length > 8 && (
                            <span className="text-xs text-tertiary">
                              +{keys.length - 8}
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        {!isProtected && (
                          <RequirePermission permission="rol_yaz">
                            <div className="flex justify-end gap-1">
                              <button
                                onClick={() => openEdit(role)}
                                className="p-2 rounded-card text-secondary hover:bg-elevated hover:text-accent transition-colors"
                                title={t("common.edit")}
                              >
                                <Pencil size={15} />
                              </button>
                              <button
                                onClick={() => setDeleteTarget(role)}
                                className="p-2 rounded-card text-secondary hover:bg-danger/10 hover:text-danger transition-colors"
                                title={t("common.delete")}
                              >
                                <Trash2 size={15} />
                              </button>
                            </div>
                          </RequirePermission>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </Card>
      </div>

      <Modal
        isOpen={isModalOpen}
        onClose={() => setModalOpen(false)}
        title={
          mode === "edit"
            ? t("admin.role_edit_title")
            : t("admin.role_create_title")
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-secondary mb-1">
              {t("admin.role_name_label")}
            </label>
            <input
              value={ad}
              onChange={(e) => setAd(e.target.value)}
              placeholder={t("admin.role_name_placeholder")}
              className="w-full bg-elevated border border-border rounded-card px-3 py-2 text-sm text-primary focus:outline-none focus:border-accent"
            />
          </div>

          <div className="space-y-4 max-h-[50vh] overflow-y-auto pr-1">
            {KNOWN_PERMISSIONS.map((grp) => (
              <div key={grp.group}>
                <p className="text-[11px] font-bold uppercase tracking-wider text-tertiary mb-1.5">
                  {grp.group}
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                  {grp.keys.map((key) => (
                    <button
                      type="button"
                      key={key}
                      onClick={() => togglePerm(key)}
                      className={`flex items-center gap-2 px-3 py-2 rounded-card border text-sm text-left transition-colors ${
                        perms[key]
                          ? "border-accent bg-accent/10 text-accent"
                          : "border-border text-secondary hover:bg-elevated"
                      }`}
                    >
                      <span
                        className={`flex h-4 w-4 items-center justify-center rounded border ${
                          perms[key]
                            ? "border-accent bg-accent text-white"
                            : "border-border"
                        }`}
                      >
                        {perms[key] && <Check size={12} />}
                      </span>
                      {key}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {formError && <p className="text-sm text-danger">{formError}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setModalOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={handleSubmit} disabled={saveMutation.isPending}>
              {saveMutation.isPending
                ? t("common.saving")
                : mode === "edit"
                  ? t("common.update")
                  : t("common.create")}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={deleteTarget != null}
        onClose={() => setDeleteTarget(null)}
        title={t("admin.role_delete_title")}
      >
        <div className="space-y-4">
          <p className="text-sm text-secondary">
            {t("admin.role_delete_body", { name: deleteTarget?.ad ?? "" })}
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setDeleteTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="danger"
              onClick={() =>
                deleteTarget && deleteMutation.mutate(deleteTarget.id)
              }
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending
                ? t("common.deleting")
                : t("common.delete")}
            </Button>
          </div>
        </div>
      </Modal>
    </ErrorBoundary>
  );
}
