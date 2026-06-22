import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { toast } from "sonner";
import {
  Loader2,
  User,
  Mail,
  Eye,
  EyeOff,
  Check,
  Shield,
  Clock,
  MapPin,
  KeyRound,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../context/AuthContext";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { Button } from "../components/ui/Button";
import { PushNotificationToggle } from "../components/profile/PushNotificationToggle";
import { QuietHoursSettings } from "../components/profile/QuietHoursSettings";
import axiosInstance from "@/services/api/axios-instance";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useLocale } from "../hooks/useLocale";
import { useTranslation } from "react-i18next";

// ── Schemas ────────────────────────────────────────────────────────────────

const profileSchema = z.object({
  ad_soyad: z.string().min(2, "İsim en az 2 karakter olmalıdır.").max(100),
});

const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, "Mevcut şifrenizi girin."),
    new_password: z
      .string()
      .min(8, "Yeni şifre en az 8 karakter olmalıdır.")
      .max(128)
      .regex(/[A-Z]/, "En az bir büyük harf içermelidir.")
      .regex(/[a-z]/, "En az bir küçük harf içermelidir.")
      .regex(/[0-9]/, "En az bir rakam içermelidir."),
    confirm_password: z.string().min(1, "Şifre tekrarını girin."),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Şifreler eşleşmiyor.",
    path: ["confirm_password"],
  });

type ProfileFormValues = z.infer<typeof profileSchema>;
type ChangePasswordFormValues = z.infer<typeof changePasswordSchema>;

// ── Helpers ────────────────────────────────────────────────────────────────

const ROLE_LABELS: Record<string, string> = {
  super_admin: "Süper Admin",
  admin: "Admin",
  driver: "Sürücü",
  user: "Operatör",
};

const ROLE_COLORS: Record<string, string> = {
  super_admin: "bg-danger/10 text-danger",
  admin: "bg-accent/10 text-accent",
  driver: "bg-success/10 text-success",
  user: "bg-secondary/10 text-secondary",
};

function formatRelative(iso: string | undefined, locale: string): string {
  if (!iso) return "Bilinmiyor";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Az önce";
  if (mins < 60) return `${mins} dakika önce`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} saat önce`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} gün önce`;
  return new Date(iso).toLocaleDateString(locale);
}

function formatDate(iso: string | undefined, locale: string): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(locale, {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

function getInitials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .map((n) => n[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

// ── Password strength ──────────────────────────────────────────────────────

interface PasswordChecks {
  length: boolean;
  upper: boolean;
  lower: boolean;
  digit: boolean;
}

function getPasswordChecks(pw: string): PasswordChecks {
  return {
    length: pw.length >= 8,
    upper: /[A-Z]/.test(pw),
    lower: /[a-z]/.test(pw),
    digit: /[0-9]/.test(pw),
  };
}

const STRENGTH_LABELS = ["", "Zayıf", "Orta", "İyi", "Güçlü"];
const STRENGTH_COLORS = [
  "",
  "bg-danger",
  "bg-warning",
  "bg-accent",
  "bg-success",
];

function PasswordStrengthBar({ password }: { password: string }) {
  if (!password) return null;
  const checks = getPasswordChecks(password);
  const score = Object.values(checks).filter(Boolean).length;

  return (
    <div className="space-y-2 pt-1">
      {/* Strength bar */}
      <div className="flex gap-1">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className={`h-1 flex-1 rounded-full transition-all duration-300 ${
              i <= score ? STRENGTH_COLORS[score] : "bg-border"
            }`}
          />
        ))}
      </div>
      <p className="text-[11px] text-tertiary">
        Şifre gücü:{" "}
        <span
          className={`font-semibold ${
            score >= 3
              ? "text-success"
              : score === 2
                ? "text-warning"
                : "text-danger"
          }`}
        >
          {STRENGTH_LABELS[score] ?? ""}
        </span>
      </p>
      {/* Requirements checklist */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
        {[
          { key: "length", label: "En az 8 karakter" },
          { key: "upper", label: "Büyük harf" },
          { key: "lower", label: "Küçük harf" },
          { key: "digit", label: "Rakam" },
        ].map(({ key, label }) => {
          const met = checks[key as keyof PasswordChecks];
          return (
            <div key={key} className="flex items-center gap-1.5">
              <Check
                size={11}
                strokeWidth={3}
                className={`flex-shrink-0 transition-colors duration-200 ${
                  met ? "text-success" : "text-border"
                }`}
              />
              <span
                className={`text-[11px] transition-colors duration-200 ${
                  met ? "text-success" : "text-tertiary"
                }`}
              >
                {label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── PasswordField ──────────────────────────────────────────────────────────

function PasswordToggleButton({
  show,
  onToggle,
}: {
  show: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="absolute right-3 top-1/2 -translate-y-1/2 text-tertiary hover:text-primary transition-colors"
      aria-label={show ? "Şifreyi gizle" : "Şifreyi göster"}
    >
      {show ? (
        <EyeOff size={15} strokeWidth={2} />
      ) : (
        <Eye size={15} strokeWidth={2} />
      )}
    </button>
  );
}

// ── Component ──────────────────────────────────────────────────────────────

export default function ProfilePage() {
  const { t } = useTranslation();
  const locale = useLocale();
  usePageTitle(t("common.my_profile", "My Profile"));
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const initials = getInitials(user?.full_name ?? user?.username ?? "?");
  const roleLabel = ROLE_LABELS[user?.role ?? ""] ?? user?.role ?? "—";
  const roleColor =
    ROLE_COLORS[user?.role ?? ""] ?? "bg-secondary/10 text-secondary";

  // ── Profile form ───────────────────────────────────────────────────────
  const {
    register: registerProfile,
    handleSubmit: handleSubmitProfile,
    formState: { errors: profileErrors, isSubmitting: isProfileSubmitting },
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: { ad_soyad: user?.full_name ?? "" },
  });

  // ── Password form ──────────────────────────────────────────────────────
  const {
    register: registerPw,
    handleSubmit: handleSubmitPw,
    reset: resetPw,
    control: pwControl,
    formState: { errors: pwErrors, isSubmitting: isPwSubmitting },
  } = useForm<ChangePasswordFormValues>({
    resolver: zodResolver(changePasswordSchema),
  });

  const newPwValue =
    useWatch({ control: pwControl, name: "new_password" }) ?? "";

  const [showCurrentPw, setShowCurrentPw] = useState(false);
  const [showNewPw, setShowNewPw] = useState(false);
  const [showConfirmPw, setShowConfirmPw] = useState(false);

  // ── Handlers ───────────────────────────────────────────────────────────

  const onProfileSubmit = async (data: ProfileFormValues) => {
    try {
      await axiosInstance.patch("/users/me", { ad_soyad: data.ad_soyad });
      toast.success("Profil bilgileri güncellendi.");
      queryClient.invalidateQueries({ queryKey: ["current-user"] });
    } catch {
      // axiosInstance interceptor already shows a toast on 4xx/5xx
    }
  };

  const onChangePasswordSubmit = async (data: ChangePasswordFormValues) => {
    try {
      await axiosInstance.post("/users/me/change-password", {
        current_password: data.current_password,
        new_password: data.new_password,
      });
      toast.success("Şifreniz başarıyla güncellendi.");
      resetPw();
    } catch {
      // axiosInstance interceptor handles error toasts
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* ── Page Title ── */}
      <div className="mb-2">
        <h1 className="text-2xl font-bold text-primary tracking-tight">
          Profilim
        </h1>
        <p className="text-sm text-secondary mt-1">
          Hesap bilgilerinizi buradan güncelleyebilirsiniz.
        </p>
      </div>

      {/* ── User Identity Hero ── */}
      <Card padding="lg">
        <div className="flex items-start gap-4">
          {/* Avatar */}
          <div className="w-16 h-16 rounded-2xl bg-accent flex items-center justify-center flex-shrink-0">
            <span className="text-xl font-black text-white tracking-tight">
              {initials}
            </span>
          </div>

          {/* Info */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-lg font-bold text-primary leading-tight truncate">
                {user?.full_name || user?.username || "—"}
              </h2>
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider ${roleColor}`}
              >
                {roleLabel}
              </span>
            </div>
            <p className="text-sm text-secondary mt-0.5 flex items-center gap-1.5">
              <Mail size={12} className="text-tertiary flex-shrink-0" />
              <span className="truncate">
                {user?.email ?? user?.username ?? "—"}
              </span>
            </p>

            {/* Meta info row */}
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
              <span className="flex items-center gap-1.5 text-[11px] text-tertiary">
                <Clock size={11} className="flex-shrink-0" />
                Son giriş:{" "}
                <span className="text-secondary font-medium">
                  {formatRelative(user?.last_login, locale)}
                </span>
              </span>
              {user?.son_giris_ip && (
                <span className="flex items-center gap-1.5 text-[11px] text-tertiary">
                  <MapPin size={11} className="flex-shrink-0" />
                  IP:{" "}
                  <span className="text-secondary font-medium font-mono">
                    {user.son_giris_ip}
                  </span>
                </span>
              )}
              {user?.created_at && (
                <span className="flex items-center gap-1.5 text-[11px] text-tertiary">
                  <User size={11} className="flex-shrink-0" />
                  Hesap:{" "}
                  <span className="text-secondary font-medium">
                    {formatDate(user.created_at, locale)}
                  </span>
                </span>
              )}
              {user?.sifre_degisim_tarihi && (
                <span className="flex items-center gap-1.5 text-[11px] text-tertiary">
                  <KeyRound size={11} className="flex-shrink-0" />
                  Şifre:{" "}
                  <span className="text-secondary font-medium">
                    {formatRelative(user.sifre_degisim_tarihi, locale)}
                  </span>
                </span>
              )}
            </div>
          </div>
        </div>
      </Card>

      {/* ── RV2.PWA — Push Notification Toggle ── */}
      <PushNotificationToggle />

      {/* ── Faz 5 — Sessiz saat ayarı ── */}
      <QuietHoursSettings />

      {/* ── Profile Info Card ── */}
      <Card padding="lg">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center text-accent">
            <User size={20} strokeWidth={1.75} />
          </div>
          <div>
            <h2 className="text-base font-bold text-primary">
              Profil Bilgileri
            </h2>
            <p className="text-xs text-tertiary mt-0.5">
              Ad soyad bilginizi güncelleyin
            </p>
          </div>
        </div>

        <form
          onSubmit={handleSubmitProfile(onProfileSubmit)}
          className="space-y-5"
        >
          {/* Email — readonly */}
          <div className="space-y-1.5">
            <label className="block text-xs font-black text-secondary uppercase tracking-widest pl-1">
              E-Posta
            </label>
            <Input
              type="text"
              value={user?.username ?? "—"}
              readOnly
              className="cursor-not-allowed text-secondary"
            />
            <p className="text-[11px] text-tertiary pl-1">
              E-posta yalnızca yönetici tarafından değiştirilebilir.
            </p>
          </div>

          {/* Ad Soyad */}
          <div className="space-y-1.5">
            <label
              htmlFor="ad_soyad"
              className="block text-xs font-black text-secondary uppercase tracking-widest pl-1"
            >
              Ad Soyad
            </label>
            <Input
              id="ad_soyad"
              type="text"
              {...registerProfile("ad_soyad")}
              error={!!profileErrors.ad_soyad}
              placeholder="Adınızı ve soyadınızı girin"
              autoComplete="name"
            />
            {profileErrors.ad_soyad && (
              <p className="text-danger text-xs font-semibold pl-1">
                {profileErrors.ad_soyad.message}
              </p>
            )}
          </div>

          <div className="pt-2">
            <Button
              type="submit"
              variant="primary"
              disabled={isProfileSubmitting}
              className="h-10 px-6 font-bold"
            >
              {isProfileSubmitting ? (
                <>
                  <Loader2
                    className="w-4 h-4 animate-spin-slow"
                    strokeWidth={2.5}
                  />
                  <span>Kaydediliyor...</span>
                </>
              ) : (
                <span>Kaydet</span>
              )}
            </Button>
          </div>
        </form>
      </Card>

      {/* ── Change Password Card ── */}
      <Card padding="lg">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-warning/10 flex items-center justify-center text-warning">
            <Shield size={20} strokeWidth={1.75} />
          </div>
          <div>
            <h2 className="text-base font-bold text-primary">Şifre Değiştir</h2>
            <p className="text-xs text-tertiary mt-0.5">
              Güvenliğiniz için düzenli olarak güncelleyin
            </p>
          </div>
        </div>

        <form
          onSubmit={handleSubmitPw(onChangePasswordSubmit)}
          className="space-y-5"
        >
          {/* Current Password */}
          <div className="space-y-1.5">
            <label
              htmlFor="current_password"
              className="block text-xs font-black text-secondary uppercase tracking-widest pl-1"
            >
              Mevcut Şifre
            </label>
            <div className="relative">
              <Input
                id="current_password"
                type={showCurrentPw ? "text" : "password"}
                {...registerPw("current_password")}
                error={!!pwErrors.current_password}
                placeholder="••••••••"
                autoComplete="current-password"
                className="pr-10"
              />
              <PasswordToggleButton
                show={showCurrentPw}
                onToggle={() => setShowCurrentPw((v) => !v)}
              />
            </div>
            {pwErrors.current_password && (
              <p className="text-danger text-xs font-semibold pl-1">
                {pwErrors.current_password.message}
              </p>
            )}
          </div>

          {/* New Password */}
          <div className="space-y-1.5">
            <label
              htmlFor="new_password"
              className="block text-xs font-black text-secondary uppercase tracking-widest pl-1"
            >
              Yeni Şifre
            </label>
            <div className="relative">
              <Input
                id="new_password"
                type={showNewPw ? "text" : "password"}
                {...registerPw("new_password")}
                error={!!pwErrors.new_password}
                placeholder="••••••••"
                autoComplete="new-password"
                className="pr-10"
              />
              <PasswordToggleButton
                show={showNewPw}
                onToggle={() => setShowNewPw((v) => !v)}
              />
            </div>
            {pwErrors.new_password && (
              <p className="text-danger text-xs font-semibold pl-1">
                {pwErrors.new_password.message}
              </p>
            )}
            <PasswordStrengthBar password={newPwValue} />
          </div>

          {/* Confirm Password */}
          <div className="space-y-1.5">
            <label
              htmlFor="confirm_password"
              className="block text-xs font-black text-secondary uppercase tracking-widest pl-1"
            >
              Yeni Şifre Tekrar
            </label>
            <div className="relative">
              <Input
                id="confirm_password"
                type={showConfirmPw ? "text" : "password"}
                {...registerPw("confirm_password")}
                error={!!pwErrors.confirm_password}
                placeholder="••••••••"
                autoComplete="new-password"
                className="pr-10"
              />
              <PasswordToggleButton
                show={showConfirmPw}
                onToggle={() => setShowConfirmPw((v) => !v)}
              />
            </div>
            {pwErrors.confirm_password && (
              <p className="text-danger text-xs font-semibold pl-1">
                {pwErrors.confirm_password.message}
              </p>
            )}
          </div>

          <div className="pt-2">
            <Button
              type="submit"
              variant="primary"
              disabled={isPwSubmitting}
              className="h-10 px-6 font-bold"
            >
              {isPwSubmitting ? (
                <>
                  <Loader2
                    className="w-4 h-4 animate-spin-slow"
                    strokeWidth={2.5}
                  />
                  <span>Güncelleniyor...</span>
                </>
              ) : (
                <span>Şifremi Güncelle</span>
              )}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
