import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import type { LeakageStats, MaintenanceVehicle } from "@/api/anomalies";
import { useLocale } from "../../hooks/useLocale";
import { formatMaintenanceReason } from "../../lib/status-labels";

// ─── LeakageSummary ──────────────────────────────────────────────────────────

interface LeakageStat {
  label: string;
  value: string;
  unit: string;
}

export function LeakageSummary({ leakage }: { leakage: LeakageStats }) {
  const { t } = useTranslation();
  const stats: LeakageStat[] = [
    {
      label: t("alerts.route_deviation"),
      value: leakage.route_deviation_km.toFixed(0),
      unit: "km",
    },
    {
      label: t("alerts.deviation_cost"),
      value: leakage.route_deviation_cost.toFixed(0),
      unit: "₺",
    },
    {
      label: t("alerts.fuel_gap"),
      value: leakage.fuel_gap_liters.toFixed(0),
      unit: "L",
    },
    {
      label: t("alerts.fuel_gap_cost"),
      value: leakage.fuel_gap_cost.toFixed(0),
      unit: "₺",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="rounded-card border border-border bg-elevated px-4 py-3"
        >
          <p className="text-[10px] font-bold uppercase tracking-widest text-secondary">
            {stat.label}
          </p>
          <p className="mt-1 text-xl font-bold text-primary">
            {stat.value}
            <span className="ml-1 text-sm font-medium text-secondary">
              {stat.unit}
            </span>
          </p>
        </div>
      ))}
    </div>
  );
}

// ─── Severity Badge ───────────────────────────────────────────────────────────

function SeverityBadge({ severity }: { severity: string }) {
  const { t } = useTranslation();
  const styles: Record<string, string> = {
    critical: "border-danger/30 bg-danger/10 text-danger",
    high: "border-warning/30 bg-warning/10 text-warning",
    medium: "border-info/30 bg-info/10 text-info",
    low: "border-border bg-elevated text-secondary",
  };
  const labels: Record<string, string> = {
    critical: t("alerts.severity_critical"),
    high: t("alerts.severity_high"),
    medium: t("alerts.severity_medium"),
    low: t("alerts.severity_low"),
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider",
        styles[severity] ?? styles.medium,
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

// ─── MaintenanceTable ─────────────────────────────────────────────────────────

export function MaintenanceTable({
  vehicles,
}: {
  vehicles: MaintenanceVehicle[];
}) {
  const { t } = useTranslation();
  const locale = useLocale();
  if (vehicles.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-secondary">
        {t("alerts.maintenance_empty")}
      </p>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t("alerts.maintenance_table_vehicle")}</TableHead>
          <TableHead>{t("alerts.maintenance_table_reason")}</TableHead>
          <TableHead>{t("alerts.maintenance_table_km")}</TableHead>
          <TableHead>{t("alerts.maintenance_table_severity")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {vehicles.map((vehicle) => (
          <TableRow key={vehicle.id}>
            <TableCell className="font-mono font-bold text-primary">
              {vehicle.plaka}
            </TableCell>
            <TableCell className="text-secondary text-sm">
              {vehicle.reason_codes
                .map((r) => formatMaintenanceReason(r, locale))
                .join(", ")}
            </TableCell>
            <TableCell className="text-secondary text-sm tabular-nums">
              {vehicle.toplam_km > 0
                ? `${vehicle.toplam_km.toLocaleString(locale)} km`
                : "—"}
            </TableCell>
            <TableCell>
              <SeverityBadge severity={vehicle.severity} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
