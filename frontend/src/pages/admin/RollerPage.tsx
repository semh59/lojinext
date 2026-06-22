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
      toast.success(mode === "edit" ? "Rol güncellendi" : "Rol oluşturuldu");
      qc.invalidateQueries({ queryKey: ["adminRoles"] });
      setModalOpen(false);
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "İşlem başarısız";
      setFormError(detail);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (roleId: number) => adminRolesApi.remove(roleId),
    onSuccess: () => {
      toast.success("Rol silindi");
      qc.invalidateQueries({ queryKey: ["adminRoles"] });
      setDeleteTarget(null);
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Rol silinemedi";
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
      setFormError("Rol adı en az 2 karakter olmalı");
      return;
    }
    if (!Object.values(perms).some(Boolean)) {
      setFormError("En az bir yetki seçin");
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
              <h1 className="text-xl font-bold text-primary">Roller</h1>
              <p className="text-sm text-secondary">
                Sistem rolleri ve yetkileri
              </p>
            </div>
          </div>
          <RequirePermission permission="rol_yaz">
            <Button onClick={openCreate}>
              <ShieldPlus size={16} className="mr-2" /> Yeni Rol
            </Button>
          </RequirePermission>
        </div>

        <Card className="p-0 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Rol</TableHead>
                <TableHead>Yetki Sayısı</TableHead>
                <TableHead>Yetkiler</TableHead>
                <TableHead className="text-right">İşlem</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-secondary">
                    Yükleniyor…
                  </TableCell>
                </TableRow>
              ) : roles.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-secondary">
                    Henüz rol yok
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
                            sistem
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        {keys.includes("*") ? "Tümü (*)" : keys.length}
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
                                title="Düzenle"
                              >
                                <Pencil size={15} />
                              </button>
                              <button
                                onClick={() => setDeleteTarget(role)}
                                className="p-2 rounded-card text-secondary hover:bg-danger/10 hover:text-danger transition-colors"
                                title="Sil"
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
        title={mode === "edit" ? "Rolü Düzenle" : "Yeni Rol Oluştur"}
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-secondary mb-1">
              Rol Adı
            </label>
            <input
              value={ad}
              onChange={(e) => setAd(e.target.value)}
              placeholder="ör. operasyon_yonetici"
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
              İptal
            </Button>
            <Button onClick={handleSubmit} disabled={saveMutation.isPending}>
              {saveMutation.isPending
                ? "Kaydediliyor…"
                : mode === "edit"
                  ? "Güncelle"
                  : "Oluştur"}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={deleteTarget != null}
        onClose={() => setDeleteTarget(null)}
        title="Rolü Sil"
      >
        <div className="space-y-4">
          <p className="text-sm text-secondary">
            <strong className="text-primary">{deleteTarget?.ad}</strong> rolünü
            silmek istediğinize emin misiniz? Bu role atanmış kullanıcı varsa
            silme reddedilir.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setDeleteTarget(null)}>
              İptal
            </Button>
            <Button
              variant="danger"
              onClick={() =>
                deleteTarget && deleteMutation.mutate(deleteTarget.id)
              }
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "Siliniyor…" : "Sil"}
            </Button>
          </div>
        </div>
      </Modal>
    </ErrorBoundary>
  );
}
