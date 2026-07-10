import { Outlet, Link, useLocation } from "react-router-dom";
import {
  Activity,
  ArrowLeft,
  BarChart2,
  Bell,
  Brain,
  Database,
  Key,
  LayoutDashboard,
  LogOut,
  Shield,
  Shuffle,
  SlidersHorizontal,
  Target,
  User as UserIcon,
  Users,
} from "lucide-react";
import { motion } from "framer-motion";

import { LojiNextLogo } from "@/components/common/LojiNextLogo";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";
import { useAdminResources } from "@/resources/useResources";
export default function AdminLayout() {
  const { adminLayoutText } = useAdminResources();
  const ADMIN_NAV = [
    {
      path: "/admin",
      label: adminLayoutText.nav.overview,
      icon: LayoutDashboard,
    },
    {
      path: "/admin/kullanicilar",
      label: adminLayoutText.nav.users,
      icon: Users,
    },
    {
      path: "/admin/roller",
      label: adminLayoutText.nav.roles,
      icon: Shield,
    },
    { path: "/admin/ml", label: adminLayoutText.nav.ml, icon: Brain },
    {
      path: "/admin/konfig",
      label: adminLayoutText.nav.configuration,
      icon: SlidersHorizontal,
    },
    {
      path: "/admin/entegrasyonlar",
      label: adminLayoutText.nav.integrations,
      icon: Key,
    },
    {
      path: "/admin/atama",
      label: adminLayoutText.nav.assignment,
      icon: Shuffle,
    },
    {
      path: "/admin/dogruluk",
      label: adminLayoutText.nav.accuracy,
      icon: Target,
    },
    {
      path: "/admin/veri",
      label: adminLayoutText.nav.dataManagement,
      icon: Database,
    },
    {
      path: "/admin/saglik",
      label: adminLayoutText.nav.systemHealth,
      icon: Activity,
    },
    {
      path: "/admin/bildirimler",
      label: adminLayoutText.nav.notifications,
      icon: Bell,
    },
    {
      path: "/admin/analitik",
      label: adminLayoutText.nav.analytics,
      icon: BarChart2,
    },
  ];
  const { user, logout } = useAuth();
  const location = useLocation();

  // Role is normalised to snake_case by AuthContext.normaliseRole()
  if (user?.role !== "super_admin" && user?.role !== "admin") {
    return (
      <div className="flex h-screen items-center justify-center bg-base">
        <div className="max-w-sm rounded-2xl border border-border bg-surface p-10 text-center shadow-sm">
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-danger/10 text-danger">
            <Shield className="h-8 w-8" />
          </div>
          <h1 className="mb-2 text-xl font-extrabold tracking-tight text-primary">
            {adminLayoutText.accessDenied.title}
          </h1>
          <p className="mb-8 text-sm text-secondary">
            {adminLayoutText.accessDenied.description}
          </p>
          <Link
            to="/trips"
            className="inline-flex w-full items-center justify-center rounded-xl bg-accent py-3 font-bold text-accent-content transition-all hover:bg-accent-dark"
          >
            {adminLayoutText.accessDenied.returnToPlatform}
          </Link>
        </div>
      </div>
    );
  }

  const currentLabel =
    ADMIN_NAV.find((item) =>
      location.pathname === "/admin"
        ? item.path === "/admin"
        : location.pathname.startsWith(item.path),
    )?.label || adminLayoutText.nav.fallback;

  return (
    <div className="flex h-screen overflow-hidden bg-base font-sans antialiased text-primary">
      <aside className="z-50 hidden w-[240px] flex-shrink-0 flex-col border-r border-border bg-surface md:flex">
        <div className="flex h-20 items-center border-b border-border px-6">
          <Link to="/trips" className="flex items-center gap-3 group">
            <LojiNextLogo iconSize={36} textSize="text-[18px]" />
          </Link>
        </div>

        <nav className="custom-scrollbar flex-1 space-y-1.5 overflow-y-auto px-4 py-6">
          {ADMIN_NAV.map((item) => {
            const isActive =
              item.path === "/admin"
                ? location.pathname === "/admin"
                : location.pathname.startsWith(item.path);

            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "group relative flex items-center gap-3.5 rounded-xl px-3 py-3 text-[14px] font-medium transition-all",
                  isActive
                    ? "bg-elevated font-bold text-accent"
                    : "text-secondary hover:bg-elevated/50 hover:text-primary",
                )}
              >
                <item.icon
                  className={cn(
                    "h-[20px] w-[20px] shrink-0",
                    isActive
                      ? "text-accent"
                      : "text-secondary group-hover:text-primary",
                  )}
                />
                {item.label}
                {isActive ? (
                  <motion.div
                    layoutId="adminActiveTab"
                    className="absolute left-0 top-[10%] bottom-[10%] w-[3px] rounded-r-full bg-accent"
                    transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                  />
                ) : null}
              </Link>
            );
          })}
        </nav>

        <div className="space-y-3 border-t border-border p-6">
          <button
            onClick={logout}
            className="group flex w-full items-center gap-3.5 rounded-xl px-3 py-3 text-[14px] font-medium text-secondary transition-all hover:bg-danger/10 hover:text-danger"
          >
            <LogOut className="h-[20px] w-[20px] text-secondary group-hover:text-danger" />
            {adminLayoutText.actions.logout}
          </button>
          <Link
            to="/trips"
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-3.5 text-[13px] font-bold uppercase tracking-wider text-surface shadow-md transition-all hover:bg-secondary"
          >
            <ArrowLeft className="h-4 w-4" />
            {adminLayoutText.actions.returnToPlatform}
          </Link>
        </div>
      </aside>

      <div className="relative flex flex-1 flex-col overflow-hidden">
        <header className="sticky top-0 z-30 flex h-20 items-center justify-between border-b border-border bg-surface/70 px-8 backdrop-blur-xl">
          <div>
            <h2 className="text-[22px] font-extrabold tracking-tight text-primary">
              {currentLabel}
            </h2>
          </div>

          <div className="flex items-center gap-5">
            <div className="flex flex-col text-right lg:flex">
              <span className="mb-0.5 text-sm font-bold tracking-tight text-primary">
                {user?.username}
              </span>
              <span className="text-[10px] font-extrabold uppercase tracking-widest text-secondary">
                {user?.role}
              </span>
            </div>
            <div className="flex size-11 items-center justify-center rounded-xl border border-border bg-surface font-bold text-accent shadow-sm">
              <UserIcon className="h-5 w-5" strokeWidth={2.5} />
            </div>
          </div>
        </header>

        <main className="relative flex-1 overflow-auto bg-base p-8">
          <div className="mx-auto w-full max-w-[1280px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
