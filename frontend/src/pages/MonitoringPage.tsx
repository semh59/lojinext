import { useState } from "react";
import { Bell, Brain, Trash2 } from "lucide-react";
import { useMonitoringSocket } from "@/components/monitoring/useMonitoringSocket";
import { NotificationsTab } from "@/components/monitoring/NotificationsTab";
import { TrainingTab } from "@/components/monitoring/TrainingTab";
import { Button } from "@/components/ui/Button";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useAuth } from "@/context/AuthContext";
import { useTranslation } from "react-i18next";

type Tab = "notifications" | "training";

interface TabConfig {
  id: Tab;
  label: string;
  icon: typeof Bell;
  badge?: number;
}

export default function MonitoringPage() {
  const { t } = useTranslation();
  usePageTitle(t("nav.notifications", "Notifications"));
  const [activeTab, setActiveTab] = useState<Tab>("notifications");
  const { status, notifications, clearNotifications, reconnect } =
    useMonitoringSocket();
  const { user } = useAuth();

  const isAdmin = user?.role === "admin" || user?.role === "super_admin";

  const tabs: TabConfig[] = [
    {
      id: "notifications",
      label: t("monitoring.tab_notifications", "Notifications"),
      icon: Bell,
      badge: notifications.length > 0 ? notifications.length : undefined,
    },
    // Error Events moved to the admin "Sistem Sağlık → Hata Analizi" page
    // (richer: severity filters, stats, resolve, live SSE) — single canonical
    // error view, no duplicate here.
    ...(isAdmin
      ? ([
          {
            id: "training",
            label: t("monitoring.tab_ml_training", "ML Training"),
            icon: Brain,
          },
        ] as TabConfig[])
      : []),
  ];

  return (
    <div data-testid="monitoring-page" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-primary tracking-tight">
            {t("monitoring.tab_notifications", "Notifications")}
          </h1>
          <p className="text-sm text-secondary mt-0.5">
            {t(
              "monitoring.page_subtitle",
              "Real-time system notifications and event stream",
            )}
          </p>
        </div>
        {activeTab === "notifications" && notifications.length > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={clearNotifications}
            className="flex items-center gap-2"
          >
            <Trash2 className="h-4 w-4" />
            {t("monitoring.clear_stream", "Clear Live Stream")}
          </Button>
        )}
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-border">
        {tabs.map(({ id, label, icon: Icon, badge }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`relative flex items-center gap-2 px-4 py-2.5 text-sm font-semibold transition-colors border-b-2 -mb-px ${
              activeTab === id
                ? "border-accent text-accent"
                : "border-transparent text-secondary hover:text-primary"
            }`}
          >
            <Icon size={15} />
            {label}
            {badge != null && (
              <span className="inline-flex items-center justify-center h-4 min-w-4 px-1 rounded-full bg-accent text-white text-[10px] font-black">
                {badge > 99 ? "99+" : badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "notifications" && (
        <NotificationsTab
          wsNotifications={notifications}
          wsStatus={status}
          onReconnect={reconnect}
        />
      )}
      {activeTab === "training" && isAdmin && <TrainingTab />}
    </div>
  );
}
