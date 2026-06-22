import { useQuery } from "@tanstack/react-query";
import { Activity, Database, HardDrive, Server, Truck } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

import { TelegramOnayPanel } from "@/components/admin/TelegramOnayPanel";
import { Card } from "@/components/ui/Card";
import { adminOverviewText } from "@/resources/tr/admin";
import { adminHealthApi } from "@/api/admin";
import { reportService } from "@/api/reports";
import { usePageTitle } from "@/hooks/usePageTitle";

const statusColor = (status?: string) => {
  if (status === "healthy" || status === "success") return "text-emerald-500";
  if (status === "degraded" || status === "missing") return "text-amber-500";
  if (!status) return "text-secondary";
  return "text-rose-500";
};

const statusLabel = (status?: string) => {
  if (!status) return "—";
  const map: Record<string, string> = {
    healthy: "Sağlıklı",
    unhealthy: "Sorunlu",
    degraded: "Kısıtlı",
    success: "Başarılı",
    missing: "Eksik",
    error: "Hata",
  };
  return map[status] ?? status;
};

export default function AdminOverviewPage() {
  usePageTitle("Yönetim Paneli");
  const { data: dashboard } = useQuery({
    queryKey: ["admin-overview", "dashboard"],
    queryFn: () => reportService.getDashboardStats(),
    staleTime: 5 * 60 * 1000,
  });

  interface HealthResponse {
    status?: string;
    backups?: { status?: string; last_backup?: string };
    components?: { database?: { status?: string }; [key: string]: unknown };
    [key: string]: unknown;
  }

  const { data: healthRaw } = useQuery({
    queryKey: ["admin-overview", "health"],
    queryFn: () => adminHealthApi.getHealth(),
    staleTime: 30 * 1000,
    refetchInterval: 30 * 1000,
  });
  const health = healthRaw as HealthResponse | undefined;

  const { data: consumptionTrend = [] } = useQuery({
    queryKey: ["admin-overview", "consumption-trend"],
    queryFn: () => reportService.getConsumptionTrend(),
    staleTime: 10 * 60 * 1000,
  });

  const cards = [
    {
      label: adminOverviewText.cards.totalTrips,
      value: dashboard?.toplam_sefer ?? 0,
      icon: Activity,
      tone: "text-blue-500",
      iconBg: "bg-blue-500/10",
    },
    {
      label: adminOverviewText.cards.activeVehicles,
      value: dashboard?.aktif_arac ?? dashboard?.toplam_arac ?? 0,
      icon: Truck,
      tone: "text-accent",
      iconBg: "bg-accent/10",
    },
    {
      label: adminOverviewText.cards.systemStatus,
      value: statusLabel(health?.status),
      icon: Server,
      tone: statusColor(health?.status),
      iconBg: "bg-emerald-500/10",
    },
    {
      label: adminOverviewText.cards.database,
      value: statusLabel(health?.components?.database?.status),
      icon: Database,
      tone: statusColor(health?.components?.database?.status),
      iconBg: "bg-amber-500/10",
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold text-primary">
          {adminOverviewText.heading}
        </h1>
        <p className="text-sm text-secondary">
          {adminOverviewText.description}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <Card
            key={card.label}
            padding="md"
            className="glass flex items-center gap-4 border-border/50"
          >
            <div
              className={`flex h-12 w-12 items-center justify-center rounded-xl ${card.iconBg}`}
            >
              <card.icon className={`h-6 w-6 ${card.tone}`} />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-tertiary">
                {card.label}
              </p>
              <p className={`mt-0.5 text-2xl font-bold ${card.tone}`}>
                {card.value}
              </p>
            </div>
          </Card>
        ))}
      </div>

      <Card padding="lg" className="glass border-border/50">
        <TelegramOnayPanel />
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card padding="lg" className="glass border-border/50">
          <div className="space-y-4">
            <div>
              <h2 className="text-lg font-bold text-primary">
                {adminOverviewText.consumptionTrend.title}
              </h2>
              <p className="text-sm text-secondary">
                {adminOverviewText.consumptionTrend.description}
              </p>
            </div>

            {consumptionTrend.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={consumptionTrend.slice(-12)}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--border)"
                    opacity={0.6}
                  />
                  <XAxis
                    dataKey="month"
                    tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
                    unit=" L"
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    formatter={(v: number | undefined) => [
                      v != null ? `${v.toFixed(1)} L` : "",
                      "Tüketim",
                    ]}
                    contentStyle={{
                      backgroundColor: "var(--bg-surface)",
                      border: "1px solid var(--border)",
                      borderRadius: "8px",
                    }}
                    itemStyle={{ color: "var(--text-primary)" }}
                    labelStyle={{ color: "var(--text-secondary)" }}
                  />
                  <Line
                    type="monotone"
                    dataKey="consumption"
                    stroke="var(--accent)"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="rounded-xl border border-dashed border-border/60 bg-elevated/20 px-4 py-8 text-sm text-secondary">
                {adminOverviewText.consumptionTrend.empty}
              </div>
            )}
          </div>
        </Card>

        <Card padding="lg" className="glass border-border/50">
          <div className="space-y-4">
            <div>
              <h2 className="text-lg font-bold text-primary">
                {adminOverviewText.operationalHealth.title}
              </h2>
              <p className="text-sm text-secondary">
                {adminOverviewText.operationalHealth.description}
              </p>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-border/50 bg-elevated/30 p-4">
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-tertiary">
                  {adminOverviewText.operationalHealth.circuitBreakers}
                </p>
                <p className="mt-2 text-2xl font-bold text-primary">
                  {Array.isArray(health?.circuit_breakers)
                    ? health.circuit_breakers.length
                    : 0}
                </p>
              </div>

              <div className="rounded-xl border border-border/50 bg-elevated/30 p-4">
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-tertiary">
                  {adminOverviewText.operationalHealth.lastBackup}
                </p>
                <div className="mt-2 flex items-center gap-2">
                  <HardDrive
                    className={`h-5 w-5 ${statusColor(
                      health?.backups?.status,
                    )}`}
                  />
                  <span
                    className={`text-sm font-bold ${statusColor(
                      health?.backups?.status,
                    )}`}
                  >
                    {statusLabel(health?.backups?.status)}
                  </span>
                </div>
                <p className="mt-2 text-xs text-secondary">
                  {health?.backups?.last_backup
                    ? new Date(health.backups.last_backup).toLocaleString(
                        "tr-TR",
                      )
                    : adminOverviewText.operationalHealth.noBackup}
                </p>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
