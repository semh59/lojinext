import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

export type AlertTab = "all" | "leakage" | "maintenance" | "investigations";

interface Props {
  active: AlertTab;
  onChange: (tab: AlertTab) => void;
  leakageHasAlert: boolean;
  maintenanceCount: number;
  investigationsCount?: number;
}

export function SeverityFilter({
  active,
  onChange,
  leakageHasAlert,
  maintenanceCount,
  investigationsCount = 0,
}: Props) {
  const { t } = useTranslation();

  const tabs: { id: AlertTab; label: string }[] = [
    { id: "all", label: t("alerts.filter_all") },
    { id: "leakage", label: t("alerts.filter_leakage") },
    { id: "maintenance", label: t("alerts.filter_maintenance") },
    { id: "investigations", label: t("alerts.filter_investigations") },
  ];

  const counts: Record<AlertTab, number | string> = {
    all: (leakageHasAlert ? 1 : 0) + maintenanceCount + investigationsCount,
    leakage: leakageHasAlert ? 1 : 0,
    maintenance: maintenanceCount,
    investigations: investigationsCount,
  };

  return (
    <div className="flex gap-1 rounded-xl border border-border bg-surface p-1 w-fit">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={cn(
            "flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors",
            active === tab.id
              ? "bg-accent text-white shadow-sm"
              : "text-secondary hover:text-primary",
          )}
        >
          {tab.label}
          <span
            className={cn(
              "rounded-full px-1.5 py-0.5 text-[10px] font-bold",
              active === tab.id
                ? "bg-white/20 text-white"
                : "bg-elevated text-secondary",
            )}
          >
            {counts[tab.id]}
          </span>
        </button>
      ))}
    </div>
  );
}
