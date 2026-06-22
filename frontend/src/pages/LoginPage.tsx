import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useAuth } from "../context/AuthContext";
import {
  Eye,
  EyeOff,
  Loader2,
  ArrowRight,
  ArrowLeft,
  Mail,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { LojiNextLogo } from "../components/common/LojiNextLogo";
import { Input } from "../components/ui/Input";
import { Button } from "../components/ui/Button";

// Validation Schemas
const loginSchema = z.object({
  username: z.string().min(1, "Lütfen kullanıcı adı veya e-posta girin."),
  password: z.string().min(1, "Lütfen şifrenizi girin."),
});

const forgotSchema = z.object({
  email: z.string().email("Geçerli bir e-posta adresi girin."),
});

type LoginFormValues = z.infer<typeof loginSchema>;
type ForgotFormValues = z.infer<typeof forgotSchema>;

type PageMode = "login" | "forgot";

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, isAuthenticated } = useAuth();
  const [mode, setMode] = useState<PageMode>("login");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [failedAttempts, setFailedAttempts] = useState(0);
  const [lockoutTime, setLockoutTime] = useState<number | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState(0);
  const [forgotSuccess, setForgotSuccess] = useState(false);
  const [forgotLoading, setForgotLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  const {
    register: registerForgot,
    handleSubmit: handleSubmitForgot,
    formState: { errors: forgotErrors },
    reset: resetForgot,
  } = useForm<ForgotFormValues>({
    resolver: zodResolver(forgotSchema),
  });

  // Auto-redirect if already logged in (UX/Edge Case Fix)
  useEffect(() => {
    if (isAuthenticated) {
      navigate("/trips", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  // Rate Limiting Timer
  useEffect(() => {
    if (lockoutTime) {
      const timer = setInterval(() => {
        const now = Date.now();
        if (now >= lockoutTime) {
          setLockoutTime(null);
          setFailedAttempts(0);
          setError(null);
        } else {
          setRemainingSeconds(Math.ceil((lockoutTime - now) / 1000));
        }
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [lockoutTime]);

  const onForgotSubmit = async (data: ForgotFormValues) => {
    setForgotLoading(true);
    try {
      await fetch("/api/v1/auth/password-reset-request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: data.email }),
      });
      setForgotSuccess(true);
    } catch {
      // Endpoint her zaman 200 döndürür; ağ hataları minimal
      setForgotSuccess(true);
    } finally {
      setForgotLoading(false);
    }
  };

  const handleBackToLogin = () => {
    setMode("login");
    setForgotSuccess(false);
    resetForgot();
  };

  const onSubmit = async (data: LoginFormValues) => {
    setError(null);
    try {
      await login(data.username, data.password);
      navigate("/trips");
    } catch (err: any) {
      const newAttempts = failedAttempts + 1;
      setFailedAttempts(newAttempts);

      if (err.response?.status === 429 || err.message?.includes("429")) {
        const waitTime = 30 * 1000;
        setLockoutTime(Date.now() + waitTime);
        setError("Çok fazla başarısız deneme. Lütfen bir süre bekleyin.");
      } else {
        setError(err.message || "Kullanıcı adı veya şifre hatalı.");
      }
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-base relative overflow-hidden font-sans">
      <div className="w-full max-w-md px-6 relative z-10 animate-slide-up">
        <div className="flex flex-col items-center mb-12">
          <LojiNextLogo iconSize={44} textSize="text-2xl" />
        </div>

        {/* Main Glass/Surface Card */}
        <div className="bg-surface p-10 sm:p-12 rounded-[24px] border border-border shadow-lg">
          <AnimatePresence mode="wait">
            {mode === "login" ? (
              <motion.form
                key="login"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.2 }}
                onSubmit={handleSubmit(onSubmit)}
                className="space-y-8"
              >
                {/* Email / Username */}
                <div className="space-y-1.5 relative">
                  <label
                    htmlFor="username"
                    className="block text-xs font-black text-secondary uppercase tracking-widest pl-1"
                  >
                    E-Posta / Kullanıcı Adı
                  </label>
                  <Input
                    id="username"
                    type="text"
                    {...register("username")}
                    disabled={isSubmitting || !!lockoutTime}
                    error={!!errors.username}
                    placeholder="E-posta adresinizi girin"
                    autoComplete="username"
                  />
                  {errors.username && (
                    <p className="text-danger text-xs font-semibold animate-fade-in pl-1">
                      {errors.username.message}
                    </p>
                  )}
                </div>

                {/* Password */}
                <div className="space-y-1.5 relative">
                  <label
                    htmlFor="password"
                    className="block text-xs font-black text-secondary uppercase tracking-widest pl-1"
                  >
                    Şifre
                  </label>

                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      {...register("password")}
                      disabled={isSubmitting || !!lockoutTime}
                      error={!!errors.password}
                      className={cn(
                        "pr-12",
                        !showPassword && "tracking-widest",
                      )}
                      placeholder="••••••••"
                      autoComplete="current-password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      disabled={isSubmitting || !!lockoutTime}
                      aria-label={
                        showPassword ? "Şifreyi gizle" : "Şifreyi göster"
                      }
                      className="absolute right-1.5 top-1/2 -translate-y-1/2 w-7 h-7 flex items-center justify-center text-secondary hover:text-primary hover:bg-elevated rounded transition-colors focus:outline-none focus:ring-2 focus:ring-accent/5"
                    >
                      {showPassword ? (
                        <EyeOff strokeWidth={1.5} className="w-4 h-4" />
                      ) : (
                        <Eye strokeWidth={1.5} className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                  {errors.password && (
                    <p className="text-danger text-xs font-semibold animate-fade-in pl-1">
                      {errors.password.message}
                    </p>
                  )}
                </div>

                {/* Rate Limiting & Error Banner */}
                <AnimatePresence mode="popLayout">
                  {error && (
                    <motion.div
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      className="p-4 rounded-xl text-sm font-medium bg-danger/10 text-danger border border-danger/20 animate-shake"
                    >
                      {lockoutTime ? (
                        <div className="flex flex-col items-center text-center gap-1.5 pt-1">
                          <span className="font-bold text-danger">
                            Güvenlik Kilidi
                          </span>
                          Lütfen tekrar denemek için{" "}
                          <span className="font-black underline tabular-nums">
                            {remainingSeconds}
                          </span>{" "}
                          saniye bekleyin.
                        </div>
                      ) : (
                        <p className="flex items-center justify-center text-center">
                          {error}
                        </p>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Submit Button */}
                <div className="pt-4 space-y-4">
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={isSubmitting || !!lockoutTime}
                    className="w-full h-11 text-[15px] font-bold group"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2
                          className="w-5 h-5 animate-spin-slow"
                          strokeWidth={2.5}
                        />
                        <span>Giriş Yapılıyor...</span>
                      </>
                    ) : (
                      <>
                        <span>Sisteme Giriş Yap</span>
                        <ArrowRight
                          className="w-4 h-4 text-bg-base group-hover:translate-x-1 transition-transform ml-2"
                          strokeWidth={2.5}
                        />
                      </>
                    )}
                  </Button>

                  {/* Forgot Password Link */}
                  <div className="text-center">
                    <button
                      type="button"
                      onClick={() => setMode("forgot")}
                      className="text-xs text-secondary hover:text-accent transition-colors font-medium underline underline-offset-2"
                    >
                      Şifreni mi unuttun?
                    </button>
                  </div>
                </div>
              </motion.form>
            ) : (
              <motion.div
                key="forgot"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
              >
                {forgotSuccess ? (
                  <div className="space-y-6 text-center py-4">
                    <div className="w-14 h-14 rounded-2xl bg-accent-soft flex items-center justify-center mx-auto">
                      <Mail className="w-7 h-7 text-accent" strokeWidth={1.5} />
                    </div>
                    <div className="space-y-2">
                      <p className="text-sm font-semibold text-primary">
                        E-posta adresinize sıfırlama talimatı gönderildi.
                      </p>
                      <p className="text-xs text-secondary">
                        Gelen kutunuzu kontrol edin. Birkaç dakika içinde
                        ulaşmadıysa spam klasörünüze bakın.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={handleBackToLogin}
                      className="flex items-center gap-1.5 text-xs text-secondary hover:text-accent transition-colors font-medium mx-auto"
                    >
                      <ArrowLeft className="w-3.5 h-3.5" />
                      Giriş sayfasına dön
                    </button>
                  </div>
                ) : (
                  <form
                    onSubmit={handleSubmitForgot(onForgotSubmit)}
                    className="space-y-8"
                  >
                    <div className="space-y-1.5">
                      <p className="text-xs font-black text-secondary uppercase tracking-widest pl-1 mb-4">
                        Şifre Sıfırlama
                      </p>
                      <label
                        htmlFor="forgot-email"
                        className="block text-xs font-black text-secondary uppercase tracking-widest pl-1"
                      >
                        E-Posta Adresi
                      </label>
                      <Input
                        id="forgot-email"
                        type="email"
                        {...registerForgot("email")}
                        disabled={forgotLoading}
                        error={!!forgotErrors.email}
                        placeholder="E-posta adresinizi girin"
                        autoComplete="email"
                      />
                      {forgotErrors.email && (
                        <p className="text-danger text-xs font-semibold animate-fade-in pl-1">
                          {forgotErrors.email.message}
                        </p>
                      )}
                    </div>

                    <div className="pt-4 space-y-4">
                      <Button
                        type="submit"
                        variant="primary"
                        disabled={forgotLoading}
                        className="w-full h-11 text-[15px] font-bold group"
                      >
                        {forgotLoading ? (
                          <>
                            <Loader2
                              className="w-5 h-5 animate-spin-slow"
                              strokeWidth={2.5}
                            />
                            <span>Gönderiliyor...</span>
                          </>
                        ) : (
                          <span>Sıfırlama Bağlantısı Gönder</span>
                        )}
                      </Button>

                      <div className="text-center">
                        <button
                          type="button"
                          onClick={handleBackToLogin}
                          className="flex items-center gap-1.5 text-xs text-secondary hover:text-accent transition-colors font-medium mx-auto"
                        >
                          <ArrowLeft className="w-3.5 h-3.5" />
                          Geri dön
                        </button>
                      </div>
                    </div>
                  </form>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
