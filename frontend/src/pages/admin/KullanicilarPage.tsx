import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Clock,
  Edit2,
  Mail,
  Shield,
  Trash2,
  UserCheck,
  UserPlus,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import ErrorBoundary from "@/components/common/ErrorBoundary";
import { UserRolePanel } from "@/components/admin/UserRolePanel";
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
import { cn } from "@/lib/utils";
import { adminUsersText } from "@/resources/tr/admin";
import { AdminUserRecord, adminRolesApi, adminUsersApi } from "@/api/admin";
import { usePageTitle } from "@/hooks/usePageTitle";

type ModalMode = "create" | "edit";

interface FormData {
  email: string;
  ad_soyad: string;
  sifre: string;
  rol_id: string;
  aktif: boolean;
}

const EMPTY_FORM: FormData = {
  email: "",
  ad_soyad: "",
  sifre: "",
  rol_id: "",
  aktif: true,
};

function userToForm(user: AdminUserRecord): FormData {
  return {
    email: user.email ?? "",
    ad_soyad: user.ad_soyad,
    sifre: "",
    rol_id: String(user.rol?.id ?? user.rol_id ?? ""),
    aktif: user.aktif,
  };
}

function isSuperAdmin(rolAd?: string) {
  return ["super_admin", "superadmin", "Super Admin"].includes(rolAd ?? "");
}

const ROLE_LABELS: Record<string, string> = {
  super_admin: "Süper Admin",
  superadmin: "Süper Admin",
  admin: "Admin",
  user: "Kullanıcı",
  viewer: "İzleyici",
};

function formatRolAd(rolAd?: string): string {
  if (!rolAd) return "";
  return ROLE_LABELS[rolAd.toLowerCase()] ?? rolAd;
}

export default function AdminUsersPage() {
  usePageTitle("Kullanıcılar");
  const qc = useQueryClient();

  const { data: users = [], isLoading } = useQuery({
    queryKey: ["adminUsers"],
    queryFn: () => adminUsersApi.getAll(0, 100),
    staleTime: 5 * 60 * 1000,
  });

  const { data: roles = [] } = useQuery({
    queryKey: ["adminRoles"],
    queryFn: () => adminRolesApi.getAll(),
    staleTime: 10 * 60 * 1000,
  });

  const [modalMode, setModalMode] = useState<ModalMode>("create");
  const [editingUser, setEditingUser] = useState<AdminUserRecord | null>(null);
  const [isModalOpen, setModalOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<AdminUserRecord | null>(
    null,
  );
  const [form, setForm] = useState<FormData>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);

  const openCreate = () => {
    setModalMode("create");
    setEditingUser(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setModalOpen(true);
  };

  const openEdit = (user: AdminUserRecord) => {
    setModalMode("edit");
    setEditingUser(user);
    setForm(userToForm(user));
    setFormError(null);
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setFormError(null);
  };

  const createMutation = useMutation({
    mutationFn: adminUsersApi.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["adminUsers"] });
      toast.success("Kullanıcı oluşturuldu");
      closeModal();
    },
    onError: (err: Error) => {
      setFormError(err.message);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: Parameters<typeof adminUsersApi.update>[1];
    }) => adminUsersApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["adminUsers"] });
      toast.success("Kullanıcı güncellendi");
      closeModal();
    },
    onError: (err: Error) => {
      setFormError(err.message);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: adminUsersApi.delete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["adminUsers"] });
      toast.success("Kullanıcı silindi");
      setDeleteTarget(null);
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const isBusy = createMutation.isPending || updateMutation.isPending;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!form.email.trim()) return setFormError("E-posta zorunludur");
    if (!form.ad_soyad.trim()) return setFormError("Ad Soyad zorunludur");
    if (modalMode === "create" && !form.sifre)
      return setFormError("Şifre zorunludur");
    if (!form.rol_id) return setFormError("Rol seçimi zorunludur");

    const rolId = Number(form.rol_id);
    if (isNaN(rolId)) return setFormError("Geçerli bir rol seçin");

    if (modalMode === "create") {
      createMutation.mutate({
        email: form.email.trim(),
        ad_soyad: form.ad_soyad.trim(),
        sifre: form.sifre,
        rol_id: rolId,
        aktif: form.aktif,
      });
    } else if (editingUser?.id != null) {
      const payload: Parameters<typeof adminUsersApi.update>[1] = {
        email: form.email.trim(),
        ad_soyad: form.ad_soyad.trim(),
        rol_id: rolId,
        aktif: form.aktif,
      };
      if (form.sifre) payload.sifre = form.sifre;
      updateMutation.mutate({ id: editingUser.id, data: payload });
    }
  };

  const field = (key: keyof FormData) => ({
    value: form[key] as string,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm((prev) => ({ ...prev, [key]: e.target.value })),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold text-primary">
            {adminUsersText.heading}
          </h1>
          <p className="text-sm text-secondary">{adminUsersText.description}</p>
        </div>
        <Button
          variant="primary"
          onClick={openCreate}
          className="h-11 rounded-xl px-6 text-xs font-bold uppercase tracking-widest shadow-md shadow-accent/20"
        >
          <UserPlus size={18} className="mr-2" />
          {adminUsersText.addUser}
        </Button>
      </div>

      <Card
        padding="none"
        className="overflow-hidden border-border/50 shadow-sm glass"
      >
        <ErrorBoundary>
          {isLoading ? (
            <div className="flex h-80 flex-col items-center justify-center gap-4">
              <div className="h-10 w-10 animate-spin rounded-full border-[3px] border-accent/10 border-t-accent" />
              <p className="animate-pulse text-[10px] font-black uppercase tracking-[0.2em] text-tertiary">
                {adminUsersText.loading}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader className="bg-elevated">
                  <TableRow className="border-border/30">
                    <TableHead className="py-4 pl-6 text-[10px] font-black uppercase tracking-widest text-tertiary">
                      <div className="flex items-center gap-2">
                        <Mail size={12} />
                        {adminUsersText.headers.identity}
                      </div>
                    </TableHead>
                    <TableHead className="py-4 text-[10px] font-black uppercase tracking-widest text-tertiary">
                      {adminUsersText.headers.fullName}
                    </TableHead>
                    <TableHead className="py-4 text-[10px] font-black uppercase tracking-widest text-tertiary">
                      <div className="flex items-center gap-2">
                        <Shield size={12} />
                        {adminUsersText.headers.role}
                      </div>
                    </TableHead>
                    <TableHead className="py-4 text-[10px] font-black uppercase tracking-widest text-tertiary">
                      <div className="flex items-center gap-2">
                        <UserCheck size={12} />
                        {adminUsersText.headers.status}
                      </div>
                    </TableHead>
                    <TableHead className="py-4 text-[10px] font-black uppercase tracking-widest text-tertiary">
                      <div className="flex items-center gap-2">
                        <Clock size={12} />
                        {adminUsersText.headers.lastLogin}
                      </div>
                    </TableHead>
                    <TableHead className="py-4 pr-6 text-right text-[10px] font-black uppercase tracking-widest text-tertiary">
                      İşlemler
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((user) => (
                    <TableRow
                      key={user.id}
                      className="group border-border/20 transition-colors hover:bg-elevated"
                    >
                      <TableCell className="py-4 pl-6">
                        <div className="flex flex-col">
                          <span className="text-sm font-bold text-primary transition-colors group-hover:text-accent">
                            {user.email}
                          </span>
                          <span className="text-[10px] font-medium text-tertiary">
                            {adminUsersText.userId(user.id)}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="py-4 text-sm font-semibold text-secondary">
                        {user.ad_soyad}
                      </TableCell>
                      <TableCell className="py-4">
                        <Badge
                          variant={
                            isSuperAdmin(user.rol?.ad) ? "warning" : "default"
                          }
                          className={cn(
                            "rounded-md border-opacity-20 px-2.5 py-0.5 text-[10px] font-black uppercase tracking-tighter",
                            isSuperAdmin(user.rol?.ad)
                              ? "border-amber-500 bg-amber-500/5 text-amber-600"
                              : "border-slate-500 bg-slate-500/5 text-slate-500",
                          )}
                        >
                          {formatRolAd(user.rol?.ad) ||
                            adminUsersText.unassignedRole}
                        </Badge>
                      </TableCell>
                      <TableCell className="py-4">
                        <div className="flex items-center gap-1.5">
                          <div
                            className={cn(
                              "h-1.5 w-1.5 rounded-full",
                              user.aktif
                                ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"
                                : "bg-rose-500",
                            )}
                          />
                          <span
                            className={cn(
                              "text-[11px] font-bold uppercase tracking-tight",
                              user.aktif ? "text-emerald-600" : "text-rose-600",
                            )}
                          >
                            {user.aktif
                              ? adminUsersText.statuses.active
                              : adminUsersText.statuses.passive}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="py-4 text-xs font-medium text-tertiary">
                        {user.son_giris
                          ? new Date(user.son_giris).toLocaleDateString(
                              "tr-TR",
                              {
                                day: "2-digit",
                                month: "short",
                                year: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                              },
                            )
                          : "---"}
                      </TableCell>
                      <TableCell className="py-4 pr-6 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEdit(user)}
                            className="group/btn h-9 rounded-lg px-3 transition-all hover:bg-accent/5 hover:text-accent"
                            aria-label={adminUsersText.actions.edit}
                          >
                            <Edit2
                              size={14}
                              className="transition-transform group-hover/btn:scale-110"
                            />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setDeleteTarget(user)}
                            className="group/btn h-9 rounded-lg px-3 transition-all hover:bg-danger/5 hover:text-danger"
                            aria-label="Sil"
                          >
                            <Trash2
                              size={14}
                              className="transition-transform group-hover/btn:scale-110"
                            />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {users.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} className="h-40 text-center">
                        <div className="flex flex-col items-center justify-center gap-2 opacity-40">
                          <Users size={32} className="text-secondary" />
                          <p className="text-xs font-bold uppercase tracking-widest text-secondary">
                            {adminUsersText.empty}
                          </p>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          )}
        </ErrorBoundary>
      </Card>

      {/* Create / Edit Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={closeModal}
        title={
          modalMode === "create"
            ? "Yeni Kullanıcı Oluştur"
            : "Kullanıcıyı Düzenle"
        }
        size="md"
      >
        <UserRolePanel
          form={form}
          formError={formError}
          modalMode={modalMode}
          roles={roles}
          isBusy={isBusy}
          onSubmit={handleSubmit}
          onClose={closeModal}
          onFieldChange={field}
          onRolChange={(value) =>
            setForm((prev) => ({ ...prev, rol_id: value }))
          }
          onAktifToggle={() =>
            setForm((prev) => ({ ...prev, aktif: !prev.aktif }))
          }
        />
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Kullanıcıyı Sil"
        size="sm"
      >
        <p className="mb-6 text-sm text-secondary">
          <span className="font-bold text-primary">
            {deleteTarget?.ad_soyad}
          </span>{" "}
          adlı kullanıcıyı kalıcı olarak silmek istediğinize emin misiniz? Bu
          işlem geri alınamaz.
        </p>
        <div className="flex justify-end gap-3">
          <Button
            variant="ghost"
            onClick={() => setDeleteTarget(null)}
            disabled={deleteMutation.isPending}
          >
            İptal
          </Button>
          <Button
            variant="danger"
            onClick={() =>
              deleteTarget?.id != null && deleteMutation.mutate(deleteTarget.id)
            }
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? "Siliniyor..." : "Evet, Sil"}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
