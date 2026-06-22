import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Database,
  HardDrive,
  RefreshCw,
  Server,
  Wifi,
  WifiOff,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import { useNotify } from "@/context/NotificationContext";
import { adminHealthText } from "@/resources/tr/admin";
import { adminHealthApi } from "@/api/admin";
import { errorService } from "@/services/api/error-service";
import type { BackendErrorEvent } from "@/services/api/error-service";
import { useEventSource } from "@/hooks/use-event-source";
import { usePageTitle } from "@/hooks/usePageTitle";

type Tab = "health" | "errors";

const LAYERS = [
  "",
  "db",
  "celery",
  "service",
  "external_api",
  "security",
  "ml",
  "frontend",
];
const SEVERITIES = ["", "debug", "info", "warning", "error", "critical"];

const severityVariant = (
  s: string,
): "danger" | "warning" | "info" | "default" => {
  if (s === "critical" || s === "error") return "danger";
  if (s === "warning") return "warning";
  if (s === "info") return "info";
  return "default";
};

function HataAnaliziTab() {
  const { notify } = useNotify();
  const qc = useQueryClient();
  const [layer, setLayer] = useState("");
  const [severity, setSeverity] = useState("");
  const [page, setPage] = useState(1);
  const [liveEvents, setLiveEvents] = useState<BackendErrorEvent[]>([]);

  const PAGE_SIZE = 25;

  const {
    data: events,
    isLoading: eventsLoading,
    isError: eventsError,
  } = useQuery({
    queryKey: ["errorEvents", layer, severity, page],
    queryFn: () =>
      errorService.getEvents({
        layer: layer || undefined,
        severity: severity || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
    staleTime: 30_000,
  });

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["errorStats"],
    queryFn: () => errorService.getStats(),
    staleTime: 60_000,
    refetchInterval: 120_000,
  });

  const resolveMutation = useMutation({
    mutationFn: (eventId: number) => errorService.resolveEvent(eventId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["errorEvents"] });
      notify("success", "Hata çözüldü olarak işaretlendi");
    },
    onError: (err: Error) => notify("error", err.message || "İşlem başarısız"),
  });

  const [sseUrl, setSseUrl] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    errorService
      .getSseToken()
      .then((url) => {
        if (!cancelled) setSseUrl(url);
      })
      .catch(() => {
        // getSseToken failed — SSE disabled until next mount
      });
    return () => {
      cancelled = true;
    };
  }, []); // mount only — the backend token has 90s TTL, reconnect handles refresh

  const liveBuffer = useRef<BackendErrorEvent[]>([]);
  const rafRef = useRef<number | null>(null);

  const onSseMessage = useCallback((data: unknown) => {
    const ev = data as BackendErrorEvent;
    if (!ev?.id) return;
    liveBuffer.current.push(ev);
    if (rafRef.current === null) {
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;
        const incoming = liveBuffer.current.splice(0);
        if (incoming.length === 0) return;
        setLiveEvents((prev) => {
          const existingIds = new Set(prev.map((e) => e.id));
          const newOnes = incoming.filter((e) => !existingIds.has(e.id));
          return [...newOnes, ...prev].slice(0, 20);
        });
      });
    }
  }, []);
  const { status: sseStatus } = useEventSource(sseUrl, {
    onMessage: onSseMessage,
  });

  // Build chart data: group last 12 hours by severity
  const chartData = useMemo(() => {
    if (!stats?.stats) return [];
    const byHour: Record<string, Record<string, number>> = {};
    stats.stats.forEach((row) => {
      const h = row.hour.slice(0, 13); // "2026-05-19T10"
      if (!byHour[h]) byHour[h] = {};
      byHour[h][row.severity] =
        (byHour[h][row.severity] ?? 0) + row.event_count;
    });
    return Object.entries(byHour)
      .sort((a, b) => a[0].localeCompare(b[0]))
      .slice(-12)
      .map(([h, counts]) => ({
        hour: h.slice(11) + ":00",
        critical: counts["critical"] ?? 0,
        error: counts["error"] ?? 0,
        warning: counts["warning"] ?? 0,
      }));
  }, [stats]);

  const totalPages = events ? Math.ceil(events.total / PAGE_SIZE) : 1;

  return (
    <div className="space-y-6">
      {/* Live stream badge */}
      <div className="flex items-center gap-2">
        {sseStatus === "open" ? (
          <span className="flex items-center gap-1.5 text-xs font-medium text-success">
            <Wifi className="h-3.5 w-3.5" /> Canlı akış bağlı
          </span>
        ) : (
          <span className="flex items-center gap-1.5 text-xs font-medium text-secondary">
            <WifiOff className="h-3.5 w-3.5" />
            {sseStatus === "connecting" ? "Bağlanıyor…" : "Bağlantı kesildi"}
          </span>
        )}
        {liveEvents.length > 0 && (
          <Badge variant="danger" className="text-xs">
            {liveEvents.length} yeni hata
          </Badge>
        )}
        {liveEvents.length > 0 && (
          <button
            className="text-xs text-accent underline"
            onClick={() => setLiveEvents([])}
          >
            temizle
          </button>
        )}
        {(sseStatus === "error" || sseStatus === "closed") && sseUrl && (
          <button
            className="text-xs text-accent underline"
            onClick={() => {
              setSseUrl("");
              errorService
                .getSseToken()
                .then((url) => setSseUrl(url))
                .catch(() => {
                  /* stay disconnected */
                });
            }}
          >
            yeniden bağlan
          </button>
        )}
      </div>

      {/* Live events banner */}
      {liveEvents.length > 0 && (
        <Card padding="none" className="border-danger/40 bg-danger/5">
          <div className="flex items-center gap-2 border-b border-danger/20 p-3">
            <AlertTriangle className="h-4 w-4 text-danger" />
            <span className="text-sm font-semibold text-primary">
              Canlı hatalar
            </span>
          </div>
          <div className="divide-y divide-border">
            {liveEvents.slice(0, 5).map((ev) => (
              <div key={ev.id} className="flex items-start gap-3 p-3">
                <Badge
                  variant={severityVariant(ev.severity)}
                  className="mt-0.5 shrink-0 text-xs"
                >
                  {ev.severity}
                </Badge>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-primary">
                    {ev.message}
                  </p>
                  <p className="text-xs text-secondary">
                    {ev.layer} · {ev.category} ·{" "}
                    {new Date(ev.last_seen).toLocaleTimeString("tr-TR")}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Hourly chart */}
      <Card padding="md" className="flex flex-col gap-4">
        <div>
          <h3 className="text-sm font-semibold text-primary">
            Saatlik Hata Dağılımı
          </h3>
          <p className="text-xs text-secondary">Son 12 saat</p>
        </div>
        {statsLoading ? (
          <div className="h-48 animate-pulse rounded-xl bg-elevated/50" />
        ) : chartData.length === 0 ? (
          <div className="flex h-48 items-center justify-center text-sm text-secondary">
            Henüz veri yok
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={192}>
            <BarChart
              data={chartData}
              margin={{ top: 0, right: 0, bottom: 0, left: -16 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="var(--border)"
                opacity={0.6}
              />
              <XAxis
                dataKey="hour"
                tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--bg-surface)",
                  border: "1px solid var(--border)",
                  borderRadius: "8px",
                }}
                itemStyle={{ color: "var(--text-primary)" }}
                labelStyle={{ color: "var(--text-secondary)" }}
              />
              <Legend
                wrapperStyle={{ fontSize: 11, color: "var(--text-secondary)" }}
              />
              <Bar
                dataKey="critical"
                stackId="a"
                fill="var(--danger)"
                name="Kritik"
              />
              <Bar
                dataKey="error"
                stackId="a"
                fill="var(--warning)"
                name="Hata"
              />
              <Bar
                dataKey="warning"
                stackId="a"
                fill="var(--info)"
                name="Uyarı"
                radius={[3, 3, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <div className="flex flex-wrap gap-1">
          {LAYERS.map((l) => (
            <button
              key={l || "all"}
              onClick={() => {
                setLayer(l);
                setPage(1);
              }}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                layer === l
                  ? "bg-accent text-white"
                  : "bg-elevated text-secondary hover:bg-border"
              }`}
            >
              {l || "Tümü"}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-1">
          {SEVERITIES.map((s) => (
            <button
              key={s || "all"}
              onClick={() => {
                setSeverity(s);
                setPage(1);
              }}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                severity === s
                  ? "bg-accent text-white"
                  : "bg-elevated text-secondary hover:bg-border"
              }`}
            >
              {s || "Tüm öncelik"}
            </button>
          ))}
        </div>
      </div>

      {/* Events table */}
      <Card padding="none">
        <div className="flex items-center justify-between border-b border-border bg-elevated/50 p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-secondary" />
            <h2 className="text-base font-bold text-primary">Hata Olayları</h2>
            {events && (
              <span className="text-xs text-secondary">
                ({events.total} toplam)
              </span>
            )}
          </div>
        </div>
        {eventsLoading ? (
          <div className="flex h-32 items-center justify-center">
            <div className="h-6 w-6 animate-spin rounded-full border-4 border-accent border-t-transparent" />
          </div>
        ) : eventsError ? (
          <div className="flex h-32 items-center justify-center text-sm text-danger">
            Hata listesi yüklenemedi. Lütfen sayfayı yenileyin.
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Öncelik</TableHead>
                <TableHead>Katman</TableHead>
                <TableHead>Kategori</TableHead>
                <TableHead>Mesaj</TableHead>
                <TableHead>Sayı</TableHead>
                <TableHead>Son görülme</TableHead>
                <TableHead className="text-right">İşlem</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events?.items.length ? (
                events.items.map((ev) => (
                  <TableRow key={ev.id}>
                    <TableCell>
                      <Badge
                        variant={severityVariant(ev.severity)}
                        className="text-xs"
                      >
                        {ev.severity}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-secondary">
                      {ev.layer}
                    </TableCell>
                    <TableCell className="text-sm text-secondary">
                      {ev.category}
                    </TableCell>
                    <TableCell className="max-w-xs">
                      <p
                        className="truncate text-sm text-primary"
                        title={ev.message}
                      >
                        {ev.message}
                      </p>
                      {ev.path && (
                        <p className="truncate text-xs text-secondary">
                          {ev.path}
                        </p>
                      )}
                    </TableCell>
                    <TableCell className="text-sm font-medium text-primary">
                      {ev.count}
                    </TableCell>
                    <TableCell className="text-xs text-secondary">
                      {new Date(ev.last_seen).toLocaleString("tr-TR")}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => resolveMutation.mutate(ev.id)}
                        disabled={resolveMutation.isPending}
                      >
                        <CheckCircle className="mr-1 h-3 w-3" />
                        Çözüldü
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="h-32 text-center text-secondary"
                  >
                    Bu filtre için hata bulunamadı
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-border p-3">
            <span className="text-xs text-secondary">
              Sayfa {page} / {totalPages}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Önceki
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Sonraki
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

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

export default function SystemHealthPage() {
  usePageTitle("Sistem Sağlığı");
  const qc = useQueryClient();
  const { notify } = useNotify();
  const [activeTab, setActiveTab] = useState<Tab>("health");

  const {
    data: health,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["adminSystemHealth"],
    queryFn: () => adminHealthApi.getHealth(),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });

  const resetCircuitBreakerMutation = useMutation({
    mutationFn: (serviceName: string) =>
      adminHealthApi.resetCircuitBreaker(serviceName),
    onSuccess: (_data, serviceName) => {
      void qc.invalidateQueries({ queryKey: ["adminSystemHealth"] });
      notify(
        "success",
        adminHealthText.notifications.resetSuccess(serviceName),
      );
    },
    onError: (err: Error) => {
      notify("error", err.message || adminHealthText.notifications.resetFailed);
    },
  });

  const backupMutation = useMutation({
    mutationFn: () => adminHealthApi.triggerBackup(),
    onSuccess: () => {
      notify("success", adminHealthText.notifications.backupStarted);
    },
    onError: (err: Error) => {
      notify(
        "error",
        err.message || adminHealthText.notifications.backupFailed,
      );
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-primary">
            {adminHealthText.heading}
          </h1>
          <p className="mt-1 text-secondary">{adminHealthText.description}</p>
        </div>
        {activeTab === "health" && (
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => void refetch()}
              disabled={isLoading}
            >
              <RefreshCw
                className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
              />
              {adminHealthText.refresh}
            </Button>
            <Button
              variant="primary"
              onClick={() => backupMutation.mutate()}
              disabled={backupMutation.isPending}
            >
              <HardDrive className="mr-2 h-4 w-4" />
              {adminHealthText.backup}
            </Button>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl bg-elevated p-1 w-fit">
        <button
          onClick={() => setActiveTab("health")}
          className={`rounded-lg px-4 py-1.5 text-sm font-medium transition-colors ${
            activeTab === "health"
              ? "bg-surface text-primary shadow-sm"
              : "text-secondary hover:text-primary"
          }`}
        >
          Sistem Durumu
        </button>
        <button
          onClick={() => setActiveTab("errors")}
          className={`rounded-lg px-4 py-1.5 text-sm font-medium transition-colors ${
            activeTab === "errors"
              ? "bg-surface text-primary shadow-sm"
              : "text-secondary hover:text-primary"
          }`}
        >
          Hata Analizi
        </button>
      </div>

      {activeTab === "health" && (
        <>
          {isLoading && !health ? (
            <div className="flex h-48 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-accent border-t-transparent" />
            </div>
          ) : health ? (
            <>
              <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                <Card padding="md" className="flex items-center gap-4">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-success/10">
                    <Activity className="h-6 w-6 text-success" />
                  </div>
                  <div>
                    <p className="text-sm font-bold uppercase tracking-widest text-secondary">
                      {adminHealthText.cards.overallStatus}
                    </p>
                    <p
                      className="mt-0.5 text-xl font-black text-primary"
                      style={{
                        color:
                          health.status === "healthy"
                            ? "var(--success)"
                            : "var(--warning)",
                      }}
                    >
                      {statusLabel(health.status)}
                    </p>
                  </div>
                </Card>
                <Card padding="md" className="flex items-center gap-4">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-info/10">
                    <Database className="h-6 w-6 text-info" />
                  </div>
                  <div>
                    <p className="text-sm font-bold uppercase tracking-widest text-secondary">
                      {adminHealthText.cards.database}
                    </p>
                    <p className="mt-0.5 text-xl font-black text-primary">
                      {statusLabel(health.components?.database?.status)}
                    </p>
                  </div>
                </Card>
                <Card padding="md" className="flex items-center gap-4">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-accent/10">
                    <Server className="h-6 w-6 text-accent" />
                  </div>
                  <div>
                    <p className="text-sm font-bold uppercase tracking-widest text-secondary">
                      {adminHealthText.cards.cache}
                    </p>
                    <p className="mt-0.5 text-xl font-black text-primary">
                      {statusLabel(health.components?.redis?.status)}
                    </p>
                  </div>
                </Card>
              </div>

              <Card padding="none">
                <div className="flex items-center justify-between border-b border-border bg-elevated/50 p-4">
                  <div className="flex items-center gap-2">
                    <Server className="h-5 w-5 text-secondary" />
                    <h2 className="text-base font-bold text-primary">
                      {adminHealthText.circuitBreakers.title}
                    </h2>
                  </div>
                </div>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>
                        {adminHealthText.circuitBreakers.serviceName}
                      </TableHead>
                      <TableHead>
                        {adminHealthText.circuitBreakers.status}
                      </TableHead>
                      <TableHead>
                        {adminHealthText.circuitBreakers.failureCount}
                      </TableHead>
                      <TableHead>
                        {adminHealthText.circuitBreakers.detail}
                      </TableHead>
                      <TableHead className="text-right">
                        {adminHealthText.circuitBreakers.actions}
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {Array.isArray(health.circuit_breakers) &&
                    health.circuit_breakers.length > 0 ? (
                      health.circuit_breakers.map((cb: any) => (
                        <TableRow key={cb.service}>
                          <TableCell className="font-medium">
                            {cb.service}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant={
                                cb.status === "closed"
                                  ? "success"
                                  : cb.status === "half-open"
                                    ? "warning"
                                    : "danger"
                              }
                            >
                              {cb.status}
                            </Badge>
                          </TableCell>
                          <TableCell>{cb.failure_count ?? 0}</TableCell>
                          <TableCell className="max-w-xs truncate text-sm text-secondary">
                            {cb.last_error || "-"}
                          </TableCell>
                          <TableCell className="text-right">
                            {cb.status !== "closed" ? (
                              <Button
                                variant="outline"
                                size="sm"
                                className="h-8"
                                onClick={() =>
                                  resetCircuitBreakerMutation.mutate(cb.service)
                                }
                                disabled={resetCircuitBreakerMutation.isPending}
                              >
                                <RefreshCw className="mr-2 h-4 w-4" />
                                {adminHealthText.circuitBreakers.reset}
                              </Button>
                            ) : null}
                          </TableCell>
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell
                          colSpan={5}
                          className="h-32 text-center text-secondary"
                        >
                          {adminHealthText.circuitBreakers.empty}
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </Card>
            </>
          ) : null}
        </>
      )}

      {activeTab === "errors" && <HataAnaliziTab />}
    </div>
  );
}
