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

// ─── LeakageSummary ──────────────────────────────────────────────────────────

interface LeakageStat {
  label: string;
  value: string;
  unit: string;
}

export function LeakageSummary({ leakage }: { leakage: LeakageStats }) {
  const stats: LeakageStat[] = [
    {
      label: "Güzergah Sapması",
      value: leakage.route_deviation_km.toFixed(0),
      unit: "km",
    },
    {
      label: "Sapma Maliyeti",
      value: leakage.route_deviation_cost.toFixed(0),
      unit: "₺",
    },
    {
      label: "Yakıt Açığı",
      value: leakage.fuel_gap_liters.toFixed(0),
      unit: "L",
    },
    {
      label: "Yakıt Açığı Maliyeti",
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
  const styles: Record<string, string> = {
    critical: "border-danger/30 bg-danger/10 text-danger",
    high: "border-warning/30 bg-warning/10 text-warning",
    medium: "border-info/30 bg-info/10 text-info",
    low: "border-border bg-elevated text-secondary",
  };
  const labels: Record<string, string> = {
    critical: "Kritik",
    high: "Acil",
    medium: "Uyarı",
    low: "Düşük",
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
  if (vehicles.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-secondary">
        Bakım adayı araç bulunmuyor.
      </p>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Araç</TableHead>
          <TableHead>Nedenler</TableHead>
          <TableHead>Toplam Km</TableHead>
          <TableHead>Önem</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {vehicles.map((vehicle) => (
          <TableRow key={vehicle.id}>
            <TableCell className="font-mono font-bold text-primary">
              {vehicle.plaka}
            </TableCell>
            <TableCell className="text-secondary text-sm">
              {vehicle.reason}
            </TableCell>
            <TableCell className="text-secondary text-sm tabular-nums">
              {vehicle.toplam_km > 0
                ? `${vehicle.toplam_km.toLocaleString("tr-TR")} km`
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
