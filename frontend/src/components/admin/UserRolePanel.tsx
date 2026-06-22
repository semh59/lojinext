import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { AdminRoleRecord } from "@/api/admin";

interface FormData {
  email: string;
  ad_soyad: string;
  sifre: string;
  rol_id: string;
  aktif: boolean;
}

type ModalMode = "create" | "edit";

interface UserRolePanelProps {
  form: FormData;
  formError: string | null;
  modalMode: ModalMode;
  roles: AdminRoleRecord[];
  isBusy: boolean;
  onSubmit: (e: React.FormEvent) => void;
  onClose: () => void;
  onFieldChange: (key: keyof FormData) => {
    value: string;
    onChange: (
      e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
    ) => void;
  };
  onRolChange: (value: string) => void;
  onAktifToggle: () => void;
}

export function UserRolePanel({
  form,
  formError,
  modalMode,
  roles,
  isBusy,
  onSubmit,
  onClose,
  onFieldChange,
  onRolChange,
  onAktifToggle,
}: UserRolePanelProps) {
  const { t } = useTranslation();
  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <Input
        label={t("profile.email_label")}
        type="email"
        placeholder="user@company.com"
        autoComplete="off"
        error={formError?.toLowerCase().includes("e-posta")}
        {...onFieldChange("email")}
      />
      <Input
        label={t("auth.name", "Full Name")}
        type="text"
        placeholder="John Smith"
        error={formError?.toLowerCase().includes("ad")}
        {...onFieldChange("ad_soyad")}
      />
      <Input
        label={
          modalMode === "create"
            ? t("auth.password")
            : t("profile.new_password") + " (" + t("common.optional") + ")"
        }
        type="password"
        placeholder={
          modalMode === "create"
            ? t("profile.req_length")
            : t("admin.user_password_required")
        }
        autoComplete="new-password"
        error={formError?.toLowerCase().includes("şifre")}
        {...onFieldChange("sifre")}
      />
      <div className="flex flex-col gap-1.5">
        <label className="text-[13px] font-medium text-primary">
          {t("admin.roles")}
        </label>
        <select
          value={form.rol_id}
          onChange={(e) => onRolChange(e.target.value)}
          className="flex h-10 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-primary outline-none focus:border-accent focus:ring-2 focus:ring-accent/5"
        >
          <option value="">{t("admin.user_role_label")}</option>
          {roles.map((r) => (
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
          onClick={onAktifToggle}
          className={cn(
            "relative h-6 w-11 rounded-full transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40",
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
            ? t("common.account_active")
            : t("common.account_passive")}
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
          onClick={onClose}
          disabled={isBusy}
        >
          {t("common.cancel")}
        </Button>
        <Button type="submit" variant="primary" disabled={isBusy}>
          {isBusy
            ? t("common.saving")
            : modalMode === "create"
              ? t("common.create")
              : t("common.save")}
        </Button>
      </div>
    </form>
  );
}
