import { useMemo, useState } from "react";
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
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import { useAuth } from "../context/AuthContext";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { Button } from "../components/ui/Button";
import { PushNotificationToggle } from "../components/profile/PushNotificationToggle";
import { QuietHoursSettings } from "../components/profile/QuietHoursSettings";
import axiosInstance from "@/services/api/axios-instance";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useLocale } from "../hooks/useLocale";

// ── Schema factories ────────────────────────────────────────────────────────

function getProfileSchema(t: TFunction) {
  return z.object({
    ad_soyad: z.string().min(2, t("profile.req_length")).max(100),
  });
}

function getChangePasswordSchema(t: TFunction) {
  return z
    .object({
      current_password: z.string().min(1, t("auth.password_required")),
      new_password: z
        .string()
        .min(8, t("profile.req_length"))
        .max(128)
        .regex(/[A-Z]/, t("profile.req_upper"))
        .regex(/[a-z]/, t("profile.req_lower"))
        .regex(/[0-9]/, t("profile.req_digit")),
      confirm_password: z.string().min(1, t("auth.password_required")),
    })
    .refine((data) => data.new_password === data.confirm_password, {
      message: t("auth.password_mismatch", "Passwords do not match."),
      path: ["confirm_password"],
    });
}

type ProfileFormValues = { ad_soyad: string };
type ChangePasswordFormValues = {
  current_password: string;
  new_password: string;
  confirm_password: string;
};

// ── Helpers ────────────────────────────────────────────────────────────────

const ROLE_COLORS: Record<string, string> = {
  super_admin: "bg-danger/10 text-danger",
  admin: "bg-accent/10 text-accent",
  driver: "bg-success/10 text-success",
  user: "bg-secondary/10 text-secondary",
};

function formatRelative(
  iso: string | undefined,
  locale: string,
  t: TFunction,
): string {
  if (!iso) return t("profile.unknown");
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return t("profile.time_just_now");
  if (mins < 60) return t("profile.time_minutes", { n: mins });
  const hours = Math.floor(mins / 60);
  if (hours < 24) return t("profile.time_hours", { n: hours });
  const days = Math.floor(hours / 24);
  if (days < 30) return t("profile.time_days", { n: days });
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

const STRENGTH_COLORS = [
  "",
  "bg-danger",
  "bg-warning",
  "bg-accent",
  "bg-success",
];

function PasswordStrengthBar({ password }: { password: string }) {
  const { t } = useTranslation();
  if (!password) return null;
  const checks = getPasswordChecks(password);
  const score = Object.values(checks).filter(Boolean).length;

  const strengthLabels = [
    "",
    t("profile.strength_weak"),
    t("profile.strength_fair"),
    t("profile.strength_good"),
    t("profile.strength_strong"),
  ];

  return (
    <div className="space-y-2 pt-1">
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
        {t("profile.password_strength")}{" "}
        <span
          className={`font-semibold ${
            score >= 3
              ? "text-success"
              : score === 2
                ? "text-warning"
                : "text-danger"
          }`}
        >
          {strengthLabels[score] ?? ""}
        </span>
      </p>
      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
        {[
          { key: "length", label: t("profile.req_length") },
          { key: "upper", label: t("profile.req_upper") },
          { key: "lower", label: t("profile.req_lower") },
          { key: "digit", label: t("profile.req_digit") },
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

// ── PasswordToggleButton ───────────────────────────────────────────────────

function PasswordToggleButton({
  show,
  onToggle,
}: {
  show: boolean;
  onToggle: () => void;
}) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      onClick={onToggle}
      className="absolute right-3 top-1/2 -translate-y-1/2 text-tertiary hover:text-primary transition-colors"
      aria-label={
        show ? t("profile.hide_password") : t("profile.show_password")
      }
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
  usePageTitle(t("common.my_profile"));
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const initials = getInitials(user?.full_name ?? user?.username ?? "?");
  const roleLabel = t(
    `profile.roles.${user?.role ?? "user"}`,
    user?.role ?? "—",
  );
  const roleColor =
    ROLE_COLORS[user?.role ?? ""] ?? "bg-secondary/10 text-secondary";

  const profileSchema = useMemo(() => getProfileSchema(t), [t]);
  const changePasswordSchema = useMemo(() => getChangePasswordSchema(t), [t]);

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
      toast.success(t("profile.update_success"));
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
      toast.success(t("profile.password_success"));
      resetPw();
    } catch {
      // axiosInstance interceptor handles error toasts
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="mb-2">
        <h1 className="text-2xl font-bold text-primary tracking-tight">
          {t("profile.page_title")}
        </h1>
        <p className="text-sm text-secondary mt-1">
          {t("profile.page_subtitle")}
        </p>
      </div>

      {/* ── User Identity Hero ── */}
      <Card padding="lg">
        <div className="flex items-start gap-4">
          <div className="w-16 h-16 rounded-2xl bg-accent flex items-center justify-center flex-shrink-0">
            <span className="text-xl font-black text-white tracking-tight">
              {initials}
            </span>
          </div>

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

            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
              <span className="flex items-center gap-1.5 text-[11px] text-tertiary">
                <Clock size={11} className="flex-shrink-0" />
                {t("profile.last_login")}{" "}
                <span className="text-secondary font-medium">
                  {formatRelative(user?.last_login, locale, t)}
                </span>
              </span>
              {user?.son_giris_ip && (
                <span className="flex items-center gap-1.5 text-[11px] text-tertiary">
                  <MapPin size={11} className="flex-shrink-0" />
                  {t("profile.ip_label")}{" "}
                  <span className="text-secondary font-medium font-mono">
                    {user.son_giris_ip}
                  </span>
                </span>
              )}
              {user?.created_at && (
                <span className="flex items-center gap-1.5 text-[11px] text-tertiary">
                  <User size={11} className="flex-shrink-0" />
                  {t("profile.account_label")}{" "}
                  <span className="text-secondary font-medium">
                    {formatDate(user.created_at, locale)}
                  </span>
                </span>
              )}
              {user?.sifre_degisim_tarihi && (
                <span className="flex items-center gap-1.5 text-[11px] text-tertiary">
                  <KeyRound size={11} className="flex-shrink-0" />
                  {t("profile.password_label")}{" "}
                  <span className="text-secondary font-medium">
                    {formatRelative(user.sifre_degisim_tarihi, locale, t)}
                  </span>
                </span>
              )}
            </div>
          </div>
        </div>
      </Card>

      {/* ── RV2.PWA — Push Notification Toggle ── */}
      <PushNotificationToggle />

      {/* ── Quiet hours settings ── */}
      <QuietHoursSettings />

      {/* ── Profile Info Card ── */}
      <Card padding="lg">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center text-accent">
            <User size={20} strokeWidth={1.75} />
          </div>
          <div>
            <h2 className="text-base font-bold text-primary">
              {t("profile.info_card_title")}
            </h2>
            <p className="text-xs text-tertiary mt-0.5">
              {t("profile.info_card_subtitle")}
            </p>
          </div>
        </div>

        <form
          onSubmit={handleSubmitProfile(onProfileSubmit)}
          className="space-y-5"
        >
          <div className="space-y-1.5">
            <label className="block text-xs font-black text-secondary uppercase tracking-widest pl-1">
              {t("profile.email_label")}
            </label>
            <Input
              type="text"
              value={user?.username ?? "—"}
              readOnly
              className="cursor-not-allowed text-secondary"
            />
            <p className="text-[11px] text-tertiary pl-1">
              {t("profile.email_admin_only")}
            </p>
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="ad_soyad"
              className="block text-xs font-black text-secondary uppercase tracking-widest pl-1"
            >
              {t("auth.name", "Full Name")}
            </label>
            <Input
              id="ad_soyad"
              type="text"
              {...registerProfile("ad_soyad")}
              error={!!profileErrors.ad_soyad}
              placeholder={t("profile.name_placeholder")}
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
                  <span>{t("profile.saving")}</span>
                </>
              ) : (
                <span>{t("profile.save")}</span>
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
            <h2 className="text-base font-bold text-primary">
              {t("profile.change_password")}
            </h2>
            <p className="text-xs text-tertiary mt-0.5">
              {t("profile.change_password_hint")}
            </p>
          </div>
        </div>

        <form
          onSubmit={handleSubmitPw(onChangePasswordSubmit)}
          className="space-y-5"
        >
          <div className="space-y-1.5">
            <label
              htmlFor="current_password"
              className="block text-xs font-black text-secondary uppercase tracking-widest pl-1"
            >
              {t("profile.current_password")}
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

          <div className="space-y-1.5">
            <label
              htmlFor="new_password"
              className="block text-xs font-black text-secondary uppercase tracking-widest pl-1"
            >
              {t("profile.new_password")}
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

          <div className="space-y-1.5">
            <label
              htmlFor="confirm_password"
              className="block text-xs font-black text-secondary uppercase tracking-widest pl-1"
            >
              {t("profile.confirm_password")}
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
                  <span>{t("profile.updating")}</span>
                </>
              ) : (
                <span>{t("profile.update_password")}</span>
              )}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
