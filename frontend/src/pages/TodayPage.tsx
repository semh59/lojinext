import { useMemo, useState } from "react";
import {
  AlertCircle,
  ListChecks,
  Loader2,
  Route as RouteIcon,
} from "lucide-react";

import { QuickActionsBar } from "@/components/today/QuickActionsBar";
import { TriageItemCard } from "@/components/today/TriageItemCard";
import { useTriage } from "@/hooks/useTriage";
import { usePageTitle } from "@/hooks/usePageTitle";
import { cn } from "@/lib/utils";
import { todayText } from "@/resources/tr/today";
import type { TriageCategory } from "@/api/today";

type ActiveTab = TriageCategory | "all";

const TABS: Array<{ id: ActiveTab; label: string }> = [
  { id: "all", label: todayText.tabs.all },
  { id: "anomaly", label: todayText.tabs.anomaly },
  { id: "maintenance", label: todayText.tabs.maintenance },
  { id: "investigation", label: todayText.tabs.investigation },
];

export default function TodayPage() {
  usePageTitle(todayText.pageTitle);
  const [activeTab, setActiveTab] = useState<ActiveTab>("all");
  const { data, isLoading, error } = useTriage();

  const filteredItems = useMemo(() => {
    if (!data?.items) return [];
    if (activeTab === "all") return data.items;
    return data.items.filter((i) => i.category === activeTab);
  }, [data?.items, activeTab]);

  const critical = filteredItems.filter((i) => i.severity === "critical");
  const pending = filteredItems.filter((i) => i.severity !== "critical");

  return (
    <div className="space-y-6 p-6">
      <header className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <ListChecks className="mt-1 h-6 w-6 text-accent" />
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-primary">
              {todayText.pageTitle}
            </h1>
            <p className="mt-1 text-sm text-secondary">
              {todayText.pageSubtitle}
            </p>
          </div>
        </div>
        {data && (
          <div className="flex gap-3 text-xs">
            <div className="rounded-card border border-border bg-elevated px-3 py-2">
              <p className="text-tertiary uppercase tracking-wider text-[10px]">
                {todayText.counters.activeTrips}
              </p>
              <p className="mt-0.5 flex items-center gap-1 font-mono font-bold text-primary">
                <RouteIcon className="h-3 w-3" />
                {data.active_trips_count}
              </p>
            </div>
            <div className="rounded-card border border-success/20 bg-success/5 px-3 py-2">
              <p className="text-tertiary uppercase tracking-wider text-[10px]">
                {todayText.counters.completedToday}
              </p>
              <p className="mt-0.5 font-mono font-bold text-success">
                ✓ {data.completed_today_count}
              </p>
            </div>
          </div>
        )}
      </header>

      {/* Tab switcher */}
      <div className="flex gap-1 rounded-xl border border-border bg-surface p-1 w-fit">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setActiveTab(t.id)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-xs font-semibold transition-all",
              activeTab === t.id
                ? "bg-accent text-white shadow-sm"
                : "text-secondary hover:text-primary",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 py-12 text-secondary">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm">{todayText.pageTitle}…</span>
        </div>
      )}

      {error && !isLoading && (
        <div className="flex items-start gap-2 rounded-modal border border-danger/30 bg-danger/5 p-4 text-sm text-danger">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          {todayText.errors.loadFailed}
        </div>
      )}

      {!isLoading && !error && data && (
        <>
          {critical.length > 0 && (
            <section className="space-y-2">
              <h2 className="flex items-center gap-2 text-sm font-bold text-danger">
                <AlertCircle className="h-4 w-4" />
                {todayText.sections.critical} ({critical.length})
              </h2>
              <div className="space-y-2">
                {critical.map((item) => (
                  <TriageItemCard key={item.id} item={item} />
                ))}
              </div>
            </section>
          )}

          {pending.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-bold text-secondary">
                {todayText.sections.pending} ({pending.length})
              </h2>
              <div className="space-y-2">
                {pending.map((item) => (
                  <TriageItemCard key={item.id} item={item} />
                ))}
              </div>
            </section>
          )}

          {filteredItems.length === 0 && (
            <div className="rounded-modal border border-success/20 bg-success/5 px-4 py-8 text-center text-sm text-success">
              ✓ {todayText.sections.empty}
            </div>
          )}

          <QuickActionsBar />
        </>
      )}
    </div>
  );
}
