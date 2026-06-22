import type { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { KpiTrendBadge } from "./KpiTrendBadge";

interface KpiItem {
  label: string;
  value: string | number;
  icon: LucideIcon;
  color: string;
  bgColor: string;
  trend?: number | null;
  trendInverted?: boolean;
}

export function KpiRow({ items }: { items: KpiItem[] }) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-3 xl:grid-cols-6">
      {items.map((item) => (
        <Card key={item.label} padding="md" className="flex items-center gap-4">
          <div
            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${item.bgColor}`}
          >
            <item.icon className={`h-6 w-6 ${item.color}`} />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-wider text-secondary truncate">
              {item.label}
            </p>
            <div className="mt-0.5 flex items-baseline gap-2">
              <p className={`text-2xl font-bold ${item.color}`}>{item.value}</p>
              {item.trend !== undefined && item.trend !== null && (
                <KpiTrendBadge trend={item.trend} invert={item.trendInverted} />
              )}
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
