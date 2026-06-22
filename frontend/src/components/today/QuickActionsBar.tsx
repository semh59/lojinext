import { useNavigate } from "react-router-dom";
import { AlertTriangle, LineChart, Plus, Users } from "lucide-react";

import { cn } from "@/lib/utils";
import { useTodayResources } from "@/resources/useResources";
interface Props {
  className?: string;
}

export function QuickActionsBar({ className }: Props) {
  const { todayText } = useTodayResources();
  const ACTIONS = [
    {
      id: "newTrip",
      icon: Plus,
      label: todayText.quickActions.newTrip,
      to: "/trips?new=1",
    },
    {
      id: "anomalies",
      icon: AlertTriangle,
      label: todayText.quickActions.anomalies,
      to: "/alerts",
    },
    {
      id: "drivers",
      icon: Users,
      label: todayText.quickActions.drivers,
      to: "/drivers",
    },
    {
      id: "executive",
      icon: LineChart,
      label: todayText.quickActions.executive,
      to: "/executive",
    },
  ] as const;
  const navigate = useNavigate();

  return (
    <div
      className={cn(
        "rounded-modal border border-border bg-surface p-4 shadow-sm",
        className,
      )}
    >
      <h3 className="mb-3 text-xs font-bold uppercase tracking-widest text-secondary">
        {todayText.quickActions.title}
      </h3>
      <div className="flex flex-wrap gap-2">
        {ACTIONS.map((a) => {
          const Icon = a.icon;
          return (
            <button
              key={a.id}
              type="button"
              onClick={() => navigate(a.to)}
              className="inline-flex items-center gap-2 rounded-card border border-border bg-elevated px-3 py-2 text-xs font-semibold text-secondary transition-all hover:border-accent/30 hover:bg-accent/5 hover:text-primary"
            >
              <Icon className="h-3.5 w-3.5" />
              {a.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
