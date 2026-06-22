import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { CheckCircle, AlertTriangle, Filter, Search } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import {
  errorService,
  type BackendErrorEvent,
  type ErrorStatsRow,
} from "@/services/api/error-service";
import { useErrorStream } from "./useErrorStream";
import { chartTheme } from "@/lib/chart-theme";
import { TraceDetailDialog } from "./TraceDetailDialog";
import { useLocale } from "../../hooks/useLocale";

// ── Chart helpers ──────────────────────────────────────────────────────────

interface ChartRow {
  saat: string;
  critical: number;
  error: number;
  warning: number;
  info: number;
}

function buildChartData(stats: ErrorStatsRow[], locale: string): ChartRow[] {
  const byHour = new Map<string, Record<string, number>>();
  stats.forEach(({ hour, severity, event_count }) => {
    if (!byHour.has(hour)) byHour.set(hour, {});
    const h = byHour.get(hour)!;
    h[severity] = (h[severity] || 0) + event_count;
  });
  return [...byHour.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-24)
    .map(([hour, counts]) => ({
      saat: new Date(hour).toLocaleTimeString(locale, {
        hour: "2-digit",
        minute: "2-digit",
      }),
      critical: counts["critical"] || 0,
      error: counts["error"] || 0,
      warning: counts["warning"] || 0,
      info: counts["info"] || 0,
    }));
}

// ── Severity & layer config ────────────────────────────────────────────────

const SEVERITY_COLORS: Record<string, string> = {
  critical: "var(--color-danger)",
  error: "#f97316",
  warning: "var(--color-warning)",
  info: "var(--color-accent)",
};

const SEVERITY_BADGE: Record<string, string> = {
  critical: "bg-danger/10 text-danger",
  error: "bg-orange-500/10 text-orange-500",
  warning: "bg-warning/10 text-warning",
  info: "bg-accent/10 text-accent",
};

const LAYERS = [
  "db",
  "api",
  "celery",
  "ml",
  "service",
  "frontend",
  "external",
  "security",
];
const SEVERITIES = ["critical", "error", "warning", "info"];

function formatTime(iso: string, locale: string) {
  try {
    return new Date(iso).toLocaleString(locale, {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

// ── FilterChip ─────────────────────────────────────────────────────────────

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1 rounded-full text-[11px] font-bold transition-colors ${
        active
          ? "bg-accent text-white"
          : "bg-elevated text-secondary hover:text-primary"
      }`}
    >
      {label}
    </button>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export function ErrorEventsTab() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const locale = useLocale();
  const [layer, setLayer] = useState<string | null>(null);
  const [severity, setSeverity] = useState<string | null>(null);
  const [showResolved, setShowResolved] = useState(false);
  const [page, setPage] = useState(1);
  const [traceDialog, setTraceDialog] = useState<string | null>(null);

  // SSE live stream (admin only — will fail silently for non-admins)
  const { liveEvents, sseStatus } = useErrorStream(true);

  const { data: eventsData, isLoading: eventsLoading } = useQuery({
    queryKey: ["error-events", layer, severity, showResolved, page],
    queryFn: () =>
      errorService.getEvents({
        layer: layer ?? undefined,
        severity: severity ?? undefined,
        resolved: showResolved,
        page,
        page_size: 20,
      }),
    staleTime: 30_000,
  });

  const { data: statsData, isLoading: statsLoading } = useQuery({
    queryKey: ["error-stats"],
    queryFn: errorService.getStats,
    staleTime: 120_000,
  });

  const resolve = useMutation({
    mutationFn: (id: number) => errorService.resolveEvent(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["error-events"] }),
  });

  const chartData = statsData ? buildChartData(statsData.stats, locale) : [];

  // Merge SSE live events with fetched list (dedup by fingerprint)
  const fetchedFingerprints = new Set(
    eventsData?.items.map((e) => e.fingerprint) ?? [],
  );
  const freshLive = liveEvents.filter(
    (e) => !fetchedFingerprints.has(e.fingerprint),
  );

  const items: BackendErrorEvent[] = [
    ...freshLive,
    ...(eventsData?.items ?? []),
  ];
  const total = (eventsData?.total ?? 0) + freshLive.length;
  const totalPages = Math.ceil((eventsData?.total ?? 0) / 20);

  return (
    <div className="space-y-5">
      {/* Hourly stats chart */}
      <Card padding="lg">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-primary">
              {t("monitoring.hourly_errors")}
            </h3>
            <p className="text-xs text-tertiary mt-0.5">
              {t("monitoring.last_24h")}
            </p>
          </div>
          <div className="flex items-center gap-1.5 text-[10px] text-tertiary">
            <span
              className={`w-2 h-2 rounded-full ${
                sseStatus === "connected"
                  ? "bg-success animate-pulse"
                  : "bg-border"
              }`}
            />
            {sseStatus === "connected"
              ? t("monitoring.stream_active")
              : t("monitoring.stream_waiting")}
          </div>
        </div>
        {statsLoading ? (
          <div className="h-40 animate-pulse rounded-card bg-elevated/50" />
        ) : chartData.length === 0 ? (
          <div className="flex h-40 items-center justify-center text-sm text-secondary">
            {t("monitoring.no_errors")}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={chartData} barSize={6}>
              <CartesianGrid {...chartTheme.grid} />
              <XAxis
                dataKey="saat"
                tick={chartTheme.tickSmall}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={chartTheme.tickSmall}
                axisLine={false}
                tickLine={false}
                allowDecimals={false}
              />
              <Tooltip {...chartTheme.tooltip} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {SEVERITIES.map((sev) => (
                <Bar
                  key={sev}
                  dataKey={sev}
                  stackId="a"
                  fill={SEVERITY_COLORS[sev]}
                  name={sev}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>

      {/* Filters */}
      <div className="space-y-2">
        <div className="flex items-center gap-2 flex-wrap">
          <Filter size={13} className="text-tertiary" />
          <span className="text-xs font-bold text-secondary uppercase tracking-wider">
            {t("monitoring.layer_label")}
          </span>
          <FilterChip
            label={t("monitoring.filter_all")}
            active={layer === null}
            onClick={() => {
              setLayer(null);
              setPage(1);
            }}
          />
          {LAYERS.map((l) => (
            <FilterChip
              key={l}
              label={l}
              active={layer === l}
              onClick={() => {
                setLayer(layer === l ? null : l);
                setPage(1);
              }}
            />
          ))}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <AlertTriangle size={13} className="text-tertiary" />
          <span className="text-xs font-bold text-secondary uppercase tracking-wider">
            {t("monitoring.severity_label")}
          </span>
          <FilterChip
            label={t("monitoring.filter_all")}
            active={severity === null}
            onClick={() => {
              setSeverity(null);
              setPage(1);
            }}
          />
          {SEVERITIES.map((s) => (
            <FilterChip
              key={s}
              label={s}
              active={severity === s}
              onClick={() => {
                setSeverity(severity === s ? null : s);
                setPage(1);
              }}
            />
          ))}
          <FilterChip
            label={
              showResolved
                ? t("monitoring.filter_resolved")
                : t("monitoring.filter_open_only")
            }
            active={showResolved}
            onClick={() => setShowResolved((v) => !v)}
          />
        </div>
      </div>

      {/* Events list */}
      {eventsLoading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-20 animate-pulse rounded-card bg-elevated/50"
            />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex h-40 flex-col items-center justify-center gap-2 rounded-modal border border-dashed border-border text-secondary">
          <CheckCircle size={24} strokeWidth={1.5} className="text-success" />
          <p className="text-sm">{t("monitoring.no_active_errors")}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((evt) => (
            <div
              key={evt.fingerprint}
              className={`rounded-card border border-l-4 bg-surface px-4 py-3 ${
                SEVERITY_BADGE[evt.severity]
                  ? `border-l-[${SEVERITY_COLORS[evt.severity]}]`
                  : "border-l-border"
              } border-border/60`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span
                      className={`inline-flex px-1.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider ${
                        SEVERITY_BADGE[evt.severity] ??
                        "bg-elevated text-secondary"
                      }`}
                    >
                      {evt.severity}
                    </span>
                    <span className="text-[10px] font-bold text-tertiary uppercase">
                      {evt.layer}
                    </span>
                    <span className="text-[10px] text-tertiary">
                      {evt.category}
                    </span>
                    {evt.count > 1 && (
                      <span className="text-[10px] font-bold text-secondary">
                        ×{evt.count}
                      </span>
                    )}
                    {evt.resolved_at && (
                      <span className="text-[10px] text-success font-semibold">
                        {t("monitoring.resolved_badge")}
                      </span>
                    )}
                  </div>
                  <p className="text-sm font-semibold text-primary leading-snug">
                    {evt.message}
                  </p>
                  {evt.path && (
                    <p className="mt-0.5 text-[11px] text-tertiary font-mono truncate">
                      {evt.path}
                    </p>
                  )}
                  <div className="mt-1 flex items-center gap-3 text-[10px] text-tertiary">
                    <span>
                      {t("monitoring.first_seen")}{" "}
                      {formatTime(evt.first_seen, locale)}
                    </span>
                    <span>Last: {formatTime(evt.last_seen, locale)}</span>
                    {evt.trace_id && (
                      <button
                        type="button"
                        onClick={() => setTraceDialog(evt.trace_id ?? null)}
                        className="inline-flex items-center gap-1 text-accent hover:underline"
                        title={t("monitoring.show_trace")}
                        data-testid="trace-open-btn"
                      >
                        <Search size={10} />
                        <span className="font-mono">
                          {evt.trace_id.slice(0, 8)}…
                        </span>
                      </button>
                    )}
                  </div>
                </div>
                {!evt.resolved_at && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => resolve.mutate(evt.id)}
                    disabled={resolve.isPending}
                    className="shrink-0 text-xs"
                  >
                    {t("monitoring.resolved_action")}
                  </Button>
                )}
              </div>
            </div>
          ))}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-xs text-tertiary">
                {t("monitoring.record_count", { n: total })}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => p - 1)}
                  disabled={page <= 1}
                >
                  {t("monitoring.prev")}
                </Button>
                <span className="flex items-center px-3 text-xs text-secondary">
                  {page} / {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={page >= totalPages}
                >
                  {t("common.next")}
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      <TraceDetailDialog
        traceId={traceDialog}
        onClose={() => setTraceDialog(null)}
      />
    </div>
  );
}
