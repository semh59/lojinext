import React, { useEffect, useRef, useState } from "react";
import { Outlet, NavLink, Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Truck,
  LogOut,
  Menu,
  X,
  Bell,
  Moon,
  Sun,
  User,
  CheckCheck,
} from "lucide-react";
import LanguageSwitcher from "./LanguageSwitcher";
import { useAuth } from "../context/AuthContext";
import { useNotify } from "../context/NotificationContext";
import type { LiveNotification } from "../context/NotificationContext";
import { buildNavGroups } from "./navGroups";
import { usePageViewTracking } from "../hooks/usePageViewTracking";
import { FeedbackButton } from "../components/feedback/FeedbackButton";
import { ChatAssistant } from "../components/ai/ChatAssistant";

function useDarkMode() {
  const [isDark, setIsDark] = useState(() => {
    const stored = localStorage.getItem("theme");
    if (stored) return stored === "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
    localStorage.setItem("theme", isDark ? "dark" : "light");
  }, [isDark]);

  return { isDark, toggle: () => setIsDark((p) => !p) };
}

function olay_tipi_label(olay_tipi: string): string {
  if (olay_tipi.includes("ANOMALY")) return "Anomali";
  if (olay_tipi.includes("DELAY") || olay_tipi.includes("SLA"))
    return "Gecikme";
  if (olay_tipi.includes("SEFER")) return "Sefer";
  return "Bildirim";
}

function NotificationPanel({
  notifications,
  onMarkAllRead,
  onClose,
}: {
  notifications: LiveNotification[];
  onMarkAllRead: () => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [onClose]);

  return (
    <div
      ref={ref}
      className="absolute right-0 top-full mt-2 w-80 rounded-2xl border border-border bg-surface shadow-xl shadow-black/10 z-50 overflow-hidden"
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <span className="text-sm font-semibold text-primary">Bildirimler</span>
        <button
          onClick={onMarkAllRead}
          className="flex items-center gap-1.5 text-xs text-secondary hover:text-accent transition-colors"
        >
          <CheckCheck size={14} />
          Tümünü okundu işaretle
        </button>
      </div>

      {notifications.length === 0 ? (
        <div className="flex items-center justify-center py-10 text-sm text-secondary">
          Henüz bildirim yok
        </div>
      ) : (
        <div className="max-h-80 overflow-y-auto divide-y divide-border/50">
          {notifications.map((n) => (
            <div
              key={n.id}
              className={`px-4 py-3 transition-colors ${
                n.read ? "" : "bg-accent/5"
              }`}
            >
              <div className="flex items-start gap-2.5">
                {!n.read && (
                  <div className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                )}
                <div className={`flex-1 min-w-0 ${n.read ? "pl-4" : ""}`}>
                  <p className="text-xs font-semibold text-primary truncate">
                    {n.baslik}
                  </p>
                  <p className="text-xs text-secondary mt-0.5 line-clamp-2">
                    {n.icerik}
                  </p>
                  <p className="text-[10px] text-tertiary mt-1">
                    {olay_tipi_label(n.olay_tipi)} ·{" "}
                    {new Date(n.olusturma_tarihi).toLocaleString("tr-TR", {
                      hour: "2-digit",
                      minute: "2-digit",
                      day: "numeric",
                      month: "short",
                    })}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const AppLayout: React.FC = () => {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  // Faz 3 — authenticated sayfa görüntülemelerini kaydet (best-effort).
  usePageViewTracking();
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isNotifOpen, setNotifOpen] = useState(false);
  const { isDark, toggle: toggleDark } = useDarkMode();

  const { unreadCount, markAllRead, liveNotifications } = useNotify();

  // Plan §6.1 — buildNavGroups pure function (test coverage)
  const navGroups = buildNavGroups(
    user,
    (key, fallback) => t(key, fallback ?? "") as string,
  );

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="min-h-screen bg-base flex flex-col md:flex-row transition-colors duration-300">
      {/* Mobile Header */}
      <div className="md:hidden flex items-center justify-between p-4 bg-surface border-b border-border shadow-sm">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-accent rounded-lg flex items-center justify-center">
            <Truck className="text-white w-5 h-5" />
          </div>
          <span className="font-bold text-lg tracking-tight">LojiNext</span>
        </div>
        <button
          onClick={() => setSidebarOpen(!isSidebarOpen)}
          className="p-2 text-primary rounded-lg hover:bg-elevated transition-colors"
          aria-label="Menüyü aç/kapat"
        >
          {isSidebarOpen ? <X /> : <Menu />}
        </button>
      </div>

      {/* Sidebar */}
      <aside
        className={[
          "fixed inset-y-0 left-0 z-50 w-64 glass transform transition-transform duration-300 ease-in-out",
          "md:relative md:translate-x-0",
          isSidebarOpen ? "translate-x-0" : "-translate-x-full",
        ].join(" ")}
      >
        <div className="h-full flex flex-col p-6">
          {/* Brand */}
          <div className="hidden md:flex items-center gap-3 mb-10 px-2">
            <div className="w-10 h-10 bg-accent rounded-xl flex items-center justify-center shadow-lg shadow-accent/20">
              <Truck className="text-white w-6 h-6" />
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-xl tracking-tight leading-none text-primary">
                LojiNext
              </span>
            </div>
          </div>

          {/* Nav */}
          <nav className="flex-1 space-y-4">
            {navGroups.map((group) => (
              <div key={group.label ?? "top"}>
                {group.label && (
                  <p className="px-4 mb-1 text-[10px] font-bold uppercase tracking-[0.2em] text-tertiary">
                    {group.label}
                  </p>
                )}
                <div className="space-y-0.5">
                  {group.items.map((item) => (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      end={item.path === "/"}
                      onClick={() => setSidebarOpen(false)}
                      className={({ isActive }) =>
                        [
                          "flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all duration-200 group",
                          isActive
                            ? "bg-accent text-white shadow-md shadow-accent/20"
                            : "text-secondary hover:bg-accent-soft hover:text-accent",
                        ].join(" ")
                      }
                    >
                      <item.icon size={18} className="shrink-0" />
                      <span className="font-medium text-sm">{item.label}</span>
                    </NavLink>
                  ))}
                </div>
              </div>
            ))}
          </nav>

          {/* Bottom */}
          <div className="pt-6 border-t border-border mt-auto space-y-3">
            <div className="px-4 flex items-center gap-2">
              <div className="flex-1">
                <LanguageSwitcher />
              </div>
              <button
                onClick={toggleDark}
                className="p-2.5 text-secondary hover:bg-elevated rounded-xl transition-colors shrink-0"
                aria-label={isDark ? "Açık moda geç" : "Koyu moda geç"}
              >
                {isDark ? <Sun size={18} /> : <Moon size={18} />}
              </button>
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 px-4 py-3 w-full text-secondary hover:text-danger hover:bg-danger/5 rounded-xl transition-all duration-200"
            >
              <LogOut size={20} className="shrink-0" />
              <span className="font-medium">
                {t("auth.logout", "Çıkış Yap")}
              </span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Top Header */}
        <header className="hidden md:flex h-20 items-center justify-between px-8 bg-surface/50 backdrop-blur-sm border-b border-border sticky top-0 z-40">
          <div />

          <div className="flex items-center gap-3">
            <div className="relative">
              <button
                onClick={() => setNotifOpen((p) => !p)}
                className="p-2.5 text-secondary hover:bg-elevated rounded-xl transition-colors relative"
                aria-label="Bildirimler"
              >
                <Bell size={20} />
                {unreadCount > 0 && (
                  <span className="absolute top-1.5 right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-danger border-2 border-surface text-[9px] font-black text-white">
                    {unreadCount > 9 ? "9+" : unreadCount}
                  </span>
                )}
              </button>
              {isNotifOpen && (
                <NotificationPanel
                  notifications={liveNotifications}
                  onMarkAllRead={() => {
                    markAllRead();
                  }}
                  onClose={() => setNotifOpen(false)}
                />
              )}
            </div>
            <div className="h-8 w-px bg-border mx-1" />
            <Link
              to="/profile"
              className="flex items-center gap-3 pl-2 hover:opacity-80 transition-opacity"
            >
              <div className="text-right">
                <p className="text-sm font-semibold text-primary leading-none">
                  {user?.full_name || user?.username || "Kullanıcı"}
                </p>
                <p className="text-[11px] text-tertiary mt-1 uppercase tracking-wider font-bold">
                  {user?.role ?? "user"}
                </p>
              </div>
              <div className="w-10 h-10 rounded-xl bg-accent-soft flex items-center justify-center text-accent ring-2 ring-transparent hover:ring-accent/20 transition-all">
                <User size={22} />
              </div>
            </Link>
          </div>
        </header>

        {/* Content */}
        <div className="p-4 md:p-8 animate-slide-up">
          <Outlet />
        </div>
      </main>

      {/* Mobile Overlay */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Faz 11 — pilot geri bildirim widget'ı */}
      <FeedbackButton />

      {/* AI Asistan — floating chat widget (yazılmıştı ama mount edilmemişti) */}
      <ChatAssistant />
    </div>
  );
};

export default AppLayout;
