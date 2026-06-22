import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  Droplets,
  TrendingDown,
  Wrench,
  Clock,
  BarChart2,
  Check,
  CheckCheck,
  X as XIcon,
  Loader2,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

import {
  SeverityFilter,
  type AlertTab,
} from "@/components/alerts/SeverityFilter";
import {
  LeakageSummary,
  MaintenanceTable,
} from "@/components/alerts/AnomalyTable";
import { InvestigationsKanban } from "@/components/alerts/InvestigationsKanban";
import { PatternList } from "@/components/alerts/PatternList";
import { AnomalyClusters } from "@/components/alerts/AnomalyClusters";
import { RequirePermission } from "@/components/auth/RequirePermission";
import { investigationService, type Investigation } from "@/api/investigations";
import { anomalyService } from "@/api/anomalies";
import { usePageTitle } from "@/hooks/usePageTitle";
import { cn } from "@/lib/utils";

const DAY_OPTIONS = [
  { label: "7 Gün", value: 7 },
  { label: "14 Gün", value: 14 },
  { label: "30 Gün", value: 30 },
  { label: "60 Gün", value: 60 },
  { label: "90 Gün", value: 90 },
];

export default function AlertsPage() {
  usePageTitle("Anomaliler");
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<AlertTab>("all");
  const [days, setDays] = useState(30);
  const [tipFilter, setTipFilter] = useState<
    "tuketim" | "maliyet" | "sefer" | undefined
  >(undefined);
  const [statusFilter, setStatusFilter] = useState<
    "open" | "acknowledged" | "resolved" | undefined
  >(undefined);
  const [resolveTarget, setResolveTarget] = useState<{
    id: number;
    plaka?: string | null;
  } | null>(null);
  const [resolveNotes, setResolveNotes] = useState("");

  // URL param desteği: dashboard/diğer widget'lardan filtered link ile gelindiğinde
  // ?days=30&tip=tuketim formatını oku ve initial state'e uygula.
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    const urlDays = Number(searchParams.get("days") ?? "");
    const urlTip = searchParams.get("tip") ?? undefined;
    const urlStatus = searchParams.get("status") ?? undefined;
    let dirty = false;
    if (
      Number.isFinite(urlDays) &&
      urlDays >= 1 &&
      urlDays <= 365 &&
      urlDays !== days
    ) {
      setDays(urlDays);
      dirty = true;
    }
    if (urlTip && ["tuketim", "maliyet", "sefer"].includes(urlTip)) {
      setTipFilter(urlTip as "tuketim" | "maliyet" | "sefer");
      dirty = true;
    }
    if (urlStatus && ["open", "acknowledged", "resolved"].includes(urlStatus)) {
      setStatusFilter(urlStatus as "open" | "acknowledged" | "resolved");
      dirty = true;
    }
    if (dirty) {
      setSearchParams({}, { replace: true });
    }
  }, []);

  const { data: insights, isLoading } = useQuery({
    queryKey: ["alerts-fleet-insights", days],
    queryFn: () => anomalyService.getFleetInsights(days),
    staleTime: 5 * 60 * 1000,
  });

  const { data: investigationsForCount } = useQuery({
    queryKey: ["investigations", "list-count", 30],
    queryFn: () => investigationService.list({ days: 30, limit: 100 }),
    staleTime: 5 * 60 * 1000,
  });
  const investigationsCount = (investigationsForCount ?? []).filter(
    (i: Investigation) => i.status !== "closed" && i.status !== "resolved",
  ).length;

  const { data: recentData, isLoading: recentLoading } = useQuery({
    queryKey: ["alerts-recent-anomalies", days, tipFilter, statusFilter],
    queryFn: () =>
      anomalyService.getRecentAnomalies({
        days,
        limit: 100,
        tip: tipFilter,
        status: statusFilter,
      }),
    staleTime: 5 * 60 * 1000,
  });

  const invalidateAnomalies = () => {
    queryClient.invalidateQueries({ queryKey: ["alerts-recent-anomalies"] });
    queryClient.invalidateQueries({ queryKey: ["fuelAnomalyWidget"] });
  };

  const acknowledgeMutation = useMutation({
    mutationFn: (anomalyId: number) => anomalyService.acknowledge(anomalyId),
    onSuccess: invalidateAnomalies,
  });

  const resolveMutation = useMutation({
    mutationFn: ({ id, notes }: { id: number; notes: string }) =>
      anomalyService.resolve(id, notes),
    onSuccess: () => {
      invalidateAnomalies();
      setResolveTarget(null);
      setResolveNotes("");
    },
  });

  const leakage = insights?.leakage;
  const maintenance = insights?.maintenance;

  const maintenanceCount =
    (maintenance?.urgent_count ?? 0) + (maintenance?.warning_count ?? 0);
  const leakageHasAlert = (leakage?.fuel_gap_liters ?? 0) > 0;
  const totalLeakageCost = leakage?.total_leakage_cost ?? 0;

  // Anomali trend — seçilen periyodu severity'ye göre günlük grupla (max 14 bar)
  const trendData = (() => {
    if (!recentData?.anomalies?.length) return [];
    const buckets: Record<
      string,
      {
        date: string;
        critical: number;
        high: number;
        medium: number;
        low: number;
      }
    > = {};
    recentData.anomalies.forEach((a) => {
      const d = a.tarih?.slice(0, 10) ?? "";
      if (!buckets[d])
        buckets[d] = { date: d, critical: 0, high: 0, medium: 0, low: 0 };
      buckets[d][a.severity as keyof (typeof buckets)[string]]++;
    });
    return Object.values(buckets)
      .sort((a, b) => a.date.localeCompare(b.date))
      .slice(-14)
      .map((b) => ({
        ...b,
        date: new Date(b.date).toLocaleDateString("tr-TR", {
          day: "numeric",
          month: "short",
        }),
      }));
  })();

  const kpis = [
    {
      label: "Yakıt Açığı",
      value: leakage ? `${Math.floor(leakage.fuel_gap_liters)} L` : "—",
      icon: Droplets,
      color: "text-warning",
      bg: "bg-warning/10",
      border: "border-warning/20",
    },
    {
      label: "Güzergah Sapması",
      value: leakage ? `${leakage.route_deviation_km.toFixed(0)} km` : "—",
      icon: AlertTriangle,
      color: "text-danger",
      bg: "bg-danger/10",
      border: "border-danger/20",
    },
    {
      label: "Toplam Maliyet Kaçağı",
      value:
        totalLeakageCost > 0
          ? totalLeakageCost.toLocaleString("tr-TR", {
              style: "currency",
              currency: "TRY",
              maximumFractionDigits: 0,
            })
          : "—",
      icon: TrendingDown,
      color: "text-danger",
      bg: "bg-danger/10",
      border: "border-danger/20",
    },
    {
      label: "Bakım Adayı",
      value: String(maintenanceCount),
      icon: Wrench,
      color: "text-info",
      bg: "bg-info/10",
      border: "border-info/20",
    },
  ];

  return (
    <div data-testid="alerts-page" className="space-y-6">
      {/* Başlık + Zaman Filtresi */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold text-primary">Anomaliler</h1>
          <p className="text-sm text-secondary">
            Filo yakıt sapmaları, bakım ihtiyaçları ve operasyonel riskler
          </p>
        </div>
        <div className="flex items-center gap-1 rounded-xl border border-border bg-surface p-1">
          {DAY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setDays(opt.value)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider transition-all",
                days === opt.value
                  ? "bg-accent text-white shadow-sm"
                  : "text-secondary hover:text-primary",
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* KPI Kartları */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {kpis.map((kpi, i) => (
          <motion.div
            key={kpi.label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.07 }}
            className={cn(
              "flex items-center gap-4 rounded-card border bg-surface p-5 shadow-sm",
              kpi.border,
            )}
          >
            <div
              className={cn(
                "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl",
                kpi.bg,
              )}
            >
              <kpi.icon size={20} className={kpi.color} />
            </div>
            <div>
              <p className="text-[11px] font-bold uppercase tracking-wider text-secondary">
                {kpi.label}
              </p>
              <p className="mt-0.5 text-xl font-bold text-primary">
                {isLoading ? (
                  <span className="inline-block h-5 w-16 animate-pulse rounded bg-elevated" />
                ) : (
                  kpi.value
                )}
              </p>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Anomali Trend Grafiği */}
      {(recentLoading || trendData.length > 0) && (
        <div className="rounded-modal border border-border bg-surface p-6 shadow-sm">
          <div className="mb-4 flex items-center gap-2">
            <BarChart2 size={16} className="text-secondary" />
            <h2 className="text-xs font-bold uppercase tracking-widest text-secondary">
              Anomali Trendi — Son {days} Gün
            </h2>
          </div>
          {recentLoading ? (
            <div className="h-32 animate-pulse rounded-card bg-elevated/50" />
          ) : (
            <ResponsiveContainer width="100%" height={120}>
              <BarChart
                data={trendData}
                barSize={12}
                margin={{ top: 4, right: 4, left: -28, bottom: 0 }}
              >
                <XAxis
                  dataKey="date"
                  axisLine={false}
                  tickLine={false}
                  tick={{
                    fill: "var(--text-secondary)",
                    fontSize: 9,
                    fontWeight: 700,
                  }}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "var(--text-secondary)", fontSize: 9 }}
                  allowDecimals={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--surface)",
                    border: "1px solid var(--border)",
                    borderRadius: "8px",
                    padding: "8px 12px",
                  }}
                  labelStyle={{ color: "var(--text-secondary)", fontSize: 10 }}
                  itemStyle={{
                    color: "var(--text-primary)",
                    fontSize: 11,
                    fontWeight: 700,
                  }}
                />
                <Bar
                  dataKey="critical"
                  name="Kritik"
                  stackId="a"
                  fill="var(--danger)"
                  radius={[0, 0, 0, 0]}
                />
                <Bar
                  dataKey="high"
                  name="Yüksek"
                  stackId="a"
                  fill="var(--warning)"
                />
                <Bar
                  dataKey="medium"
                  name="Orta"
                  stackId="a"
                  fill="var(--info)"
                />
                <Bar
                  dataKey="low"
                  name="Düşük"
                  stackId="a"
                  fill="var(--border)"
                  radius={[3, 3, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
          <div className="mt-3 flex items-center gap-4">
            {[
              { label: "Kritik", color: "bg-danger" },
              { label: "Yüksek", color: "bg-warning" },
              { label: "Orta", color: "bg-info" },
              { label: "Düşük", color: "bg-border" },
            ].map((l) => (
              <div key={l.label} className="flex items-center gap-1.5">
                <div className={cn("h-2 w-2 rounded-full", l.color)} />
                <span className="text-[10px] font-bold uppercase tracking-wider text-secondary">
                  {l.label}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sekme Filtresi */}
      <SeverityFilter
        active={activeTab}
        onChange={setActiveTab}
        leakageHasAlert={leakageHasAlert}
        maintenanceCount={maintenanceCount}
        investigationsCount={investigationsCount}
      />

      {/* İçerik Bölümleri — ayrı Card'lar */}
      {isLoading ? (
        <div className="space-y-4">
          <div className="h-40 animate-pulse rounded-modal border border-border bg-elevated/50" />
          <div className="h-64 animate-pulse rounded-modal border border-border bg-elevated/50" />
        </div>
      ) : (
        <div className="space-y-4">
          {(activeTab === "all" || activeTab === "leakage") && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-modal border border-border bg-surface p-6 shadow-sm"
            >
              <div className="mb-4 flex items-center gap-2">
                <Droplets size={14} className="text-warning" />
                <h2 className="text-xs font-bold uppercase tracking-widest text-secondary">
                  Yakıt Kaçağı Özeti
                </h2>
              </div>
              {leakage && leakage.fuel_gap_liters > 0 ? (
                <LeakageSummary leakage={leakage} />
              ) : (
                <div className="flex items-center gap-3 rounded-card border border-success/20 bg-success/5 px-4 py-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-success/10">
                    <Droplets size={14} className="text-success" />
                  </div>
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-success">
                      Temiz
                    </p>
                    <p className="mt-0.5 text-sm text-secondary">
                      Son {days} günde anormal yakıt tüketimi tespit edilmedi
                    </p>
                  </div>
                </div>
              )}
            </motion.div>
          )}

          {(activeTab === "all" || activeTab === "maintenance") &&
            maintenance && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.05 }}
                className="rounded-modal border border-border bg-surface p-6 shadow-sm"
              >
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Wrench size={14} className="text-info" />
                    <h2 className="text-xs font-bold uppercase tracking-widest text-secondary">
                      Bakım Adayları
                    </h2>
                  </div>
                  <div className="flex items-center gap-2">
                    {maintenance.urgent_count > 0 && (
                      <span className="flex items-center gap-1.5 rounded-full border border-danger/20 bg-danger/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-danger">
                        <span className="relative flex h-1.5 w-1.5">
                          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-danger opacity-75" />
                          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-danger" />
                        </span>
                        {maintenance.urgent_count} Acil
                      </span>
                    )}
                    {maintenance.warning_count > 0 && (
                      <span className="rounded-full border border-warning/20 bg-warning/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-warning">
                        {maintenance.warning_count} Uyarı
                      </span>
                    )}
                  </div>
                </div>
                {maintenance.vehicles.length === 0 ? (
                  <div className="flex items-center gap-3 rounded-card border border-success/20 bg-success/5 px-4 py-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-success/10">
                      <Wrench size={14} className="text-success" />
                    </div>
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider text-success">
                        Temiz
                      </p>
                      <p className="mt-0.5 text-sm text-secondary">
                        Bakım gerektiren araç bulunmuyor
                      </p>
                    </div>
                  </div>
                ) : (
                  <MaintenanceTable vehicles={maintenance.vehicles} />
                )}
              </motion.div>
            )}

          {activeTab === "investigations" && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 }}
              className="space-y-4"
            >
              <InvestigationsKanban />
              <PatternList />
              {/* Faz 8 — anomali kümeleri (DBSCAN pattern'leri) */}
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-secondary">
                  Anomali Kümeleri
                </h3>
                <AnomalyClusters />
              </div>
            </motion.div>
          )}

          {/* Son anomaliler — sadece 'all' sekmesinde */}
          {activeTab === "all" && recentData && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="rounded-modal border border-border bg-surface p-6 shadow-sm"
            >
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-2">
                  <Clock size={14} className="text-secondary" />
                  <h2 className="text-xs font-bold uppercase tracking-widest text-secondary">
                    Son Anomali Kayıtları
                  </h2>
                </div>

                {/* Durum filtresi */}
                <div className="flex items-center gap-1 rounded-card border border-border bg-elevated p-0.5">
                  {(
                    [
                      { id: undefined, label: "Tümü" },
                      { id: "open" as const, label: "Açık" },
                      { id: "acknowledged" as const, label: "Onaylı" },
                      { id: "resolved" as const, label: "Çözüldü" },
                    ] as const
                  ).map((opt) => (
                    <button
                      key={String(opt.id)}
                      onClick={() => setStatusFilter(opt.id ?? undefined)}
                      className={cn(
                        "rounded-card px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider transition-all",
                        statusFilter === opt.id
                          ? "bg-accent text-white"
                          : "text-secondary hover:text-primary",
                      )}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>

                {/* Tip filtresi */}
                <select
                  value={tipFilter ?? ""}
                  onChange={(e) =>
                    setTipFilter(
                      (e.target.value || undefined) as typeof tipFilter,
                    )
                  }
                  className="rounded-card border border-border bg-elevated px-2 py-1 text-[11px] font-semibold text-primary outline-none focus:border-accent"
                  aria-label="Anomali tipi"
                >
                  <option value="">Tüm Tipler</option>
                  <option value="tuketim">Tüketim</option>
                  <option value="maliyet">Maliyet</option>
                  <option value="sefer">Sefer</option>
                </select>

                <span className="ml-auto text-[10px] font-bold text-secondary">
                  {recentData.total} kayıt
                </span>
              </div>

              {recentData.anomalies.length === 0 && (
                <div className="rounded-card border border-success/20 bg-success/5 px-4 py-3 text-sm text-secondary">
                  Bu filtreyle eşleşen anomali yok.
                </div>
              )}

              <div className="space-y-2 max-h-[400px] overflow-y-auto custom-scrollbar pr-1">
                {recentData.anomalies.map((anomaly) => (
                  <div
                    key={anomaly.id}
                    className="rounded-card border border-border/50 bg-elevated p-4 transition-colors hover:border-border"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-bold text-primary">
                            {anomaly.plaka ?? `#${anomaly.kaynak_id}`}
                          </span>
                          {anomaly.sofor_adi &&
                            anomaly.sofor_adi !== "Bilinmiyor" && (
                              <span className="text-xs text-secondary">
                                — {anomaly.sofor_adi}
                              </span>
                            )}
                        </div>
                        <p className="mt-1 text-xs text-secondary">
                          {anomaly.aciklama}
                        </p>
                        {anomaly.rca_summary && (
                          <p className="mt-1 text-[10px] font-medium text-secondary/70">
                            <span className="font-bold text-secondary">
                              RCA:
                            </span>{" "}
                            {anomaly.rca_summary}
                          </p>
                        )}
                        {anomaly.suggested_action && (
                          <p className="mt-0.5 text-[10px] font-medium text-info/80">
                            → {anomaly.suggested_action}
                          </p>
                        )}
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1.5">
                        <SeverityBadge severity={anomaly.severity} />
                        <span className="text-[9px] font-bold uppercase tracking-wider text-secondary/50">
                          {new Date(anomaly.tarih).toLocaleDateString("tr-TR", {
                            day: "numeric",
                            month: "short",
                          })}
                        </span>
                        <span className="text-[9px] font-bold uppercase tracking-wider text-secondary/50">
                          {anomaly.deger.toFixed(1)} /{" "}
                          {anomaly.beklenen_deger.toFixed(1)} L
                          <span
                            className={cn(
                              "ml-1",
                              anomaly.sapma_yuzde > 0
                                ? "text-danger"
                                : "text-success",
                            )}
                          >
                            ({anomaly.sapma_yuzde > 0 ? "+" : ""}
                            {anomaly.sapma_yuzde.toFixed(1)}%)
                          </span>
                        </span>
                      </div>
                    </div>

                    {/* Eylem satırı */}
                    <div className="mt-3 flex items-center justify-end gap-2 border-t border-border/40 pt-2">
                      {anomaly.resolved_at ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-success">
                          <CheckCheck className="h-3 w-3" /> Çözüldü
                        </span>
                      ) : anomaly.acknowledged_at ? (
                        <>
                          <span className="inline-flex items-center gap-1 rounded-full bg-info/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-info">
                            <Check className="h-3 w-3" /> Onaylı
                          </span>
                          <RequirePermission permission="anomali:yonet">
                            <button
                              type="button"
                              onClick={() =>
                                setResolveTarget({
                                  id: anomaly.id,
                                  plaka: anomaly.plaka,
                                })
                              }
                              className="rounded-card border border-success/30 bg-success/5 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-success transition-colors hover:bg-success/10"
                            >
                              Çöz
                            </button>
                          </RequirePermission>
                        </>
                      ) : (
                        <RequirePermission permission="anomali:yonet">
                          <button
                            type="button"
                            disabled={
                              acknowledgeMutation.isPending &&
                              acknowledgeMutation.variables === anomaly.id
                            }
                            onClick={() =>
                              acknowledgeMutation.mutate(anomaly.id)
                            }
                            className="inline-flex items-center gap-1 rounded-card border border-info/30 bg-info/5 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-info transition-colors hover:bg-info/10 disabled:opacity-50"
                          >
                            {acknowledgeMutation.isPending &&
                            acknowledgeMutation.variables === anomaly.id ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <Check className="h-3 w-3" />
                            )}
                            Onayla
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              setResolveTarget({
                                id: anomaly.id,
                                plaka: anomaly.plaka,
                              })
                            }
                            className="inline-flex items-center gap-1 rounded-card border border-success/30 bg-success/5 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-success transition-colors hover:bg-success/10"
                          >
                            <CheckCheck className="h-3 w-3" /> Çöz
                          </button>
                        </RequirePermission>
                      )}
                    </div>

                    {anomaly.resolution_notes && (
                      <p className="mt-2 rounded-card border border-success/20 bg-success/5 px-3 py-2 text-[11px] text-secondary">
                        <span className="font-semibold text-success">
                          Çözüm:
                        </span>{" "}
                        {anomaly.resolution_notes}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </div>
      )}

      {resolveTarget && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md overflow-hidden rounded-modal border border-border bg-surface shadow-2xl">
            <div className="flex items-center justify-between border-b border-border bg-elevated/40 p-4">
              <h3 className="text-sm font-semibold text-primary">
                Anomaliyi Çöz
                {resolveTarget.plaka && (
                  <span className="ml-2 font-mono text-xs text-secondary">
                    — {resolveTarget.plaka}
                  </span>
                )}
              </h3>
              <button
                onClick={() => {
                  setResolveTarget(null);
                  setResolveNotes("");
                }}
                className="rounded-full p-1.5 text-secondary transition-colors hover:bg-elevated hover:text-primary"
                aria-label="Kapat"
              >
                <XIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-3 p-4">
              <label className="block text-[11px] font-bold uppercase tracking-wider text-secondary">
                Çözüm Notu (opsiyonel)
              </label>
              <textarea
                value={resolveNotes}
                onChange={(e) => setResolveNotes(e.target.value)}
                rows={4}
                maxLength={2000}
                placeholder="Ne yapıldı? Sahte alarm mı, gerçek bulgu mu?"
                className="w-full rounded-card border border-border bg-elevated px-3 py-2 text-sm text-primary outline-none focus:border-accent"
              />
              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => {
                    setResolveTarget(null);
                    setResolveNotes("");
                  }}
                  className="rounded-card px-3 py-1.5 text-xs font-semibold text-secondary transition-colors hover:bg-elevated hover:text-primary"
                >
                  İptal
                </button>
                <button
                  onClick={() =>
                    resolveMutation.mutate({
                      id: resolveTarget.id,
                      notes: resolveNotes.trim(),
                    })
                  }
                  disabled={resolveMutation.isPending}
                  className="inline-flex items-center gap-2 rounded-card bg-success px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-success/90 disabled:opacity-50"
                >
                  {resolveMutation.isPending && (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  )}
                  Çöz
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const styles: Record<string, string> = {
    critical: "border-danger/30 bg-danger/10 text-danger",
    high: "border-warning/30 bg-warning/10 text-warning",
    medium: "border-info/30 bg-info/10 text-info",
    low: "border-border bg-elevated text-secondary",
  };
  const labels: Record<string, string> = {
    critical: "Kritik",
    high: "Yüksek",
    medium: "Orta",
    low: "Düşük",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider",
        styles[severity] ?? styles.low,
      )}
    >
      {severity === "critical" && (
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-danger opacity-75" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-danger" />
        </span>
      )}
      {labels[severity] ?? severity}
    </span>
  );
}
