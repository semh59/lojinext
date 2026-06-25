import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CalendarClock, ShieldCheck, Truck } from "lucide-react";

import { Card } from "@/components/ui/Card";
import axiosInstance from "@/services/api/axios-instance";
import { useMaintenancePredictionsResources } from "@/resources/useResources";

interface InspectionItem {
  id: number;
  plaka: string;
  marka?: string | null;
  model?: string | null;
  tipi?: string | null;
  yil?: number | null;
  muayene_tarihi: string | null;
  days_remaining: number | null;
}

interface InspectionResp {
  expiring: InspectionItem[];
  overdue: InspectionItem[];
}

async function fetchAlerts(url: string): Promise<InspectionResp> {
  const { data } = await axiosInstance.get<InspectionResp>(url, {
    params: { within_days: 30 },
  });
  return data;
}

function Row({ item, overdue }: { item: InspectionItem; overdue: boolean }) {
  const { maintenancePredictionsText: txt } =
    useMaintenancePredictionsResources();
  const days = item.days_remaining ?? 0;
  return (
    <div className="flex items-center justify-between rounded-card border border-border bg-base px-4 py-2.5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm font-bold text-primary">
          {item.plaka}
        </span>
        <span className="text-xs text-secondary">
          {[item.marka, item.model ?? item.tipi].filter(Boolean).join(" ")}
        </span>
      </div>
      <span
        className={`text-xs font-bold ${
          overdue ? "text-danger" : "text-warning"
        }`}
      >
        {overdue
          ? txt.inspection.daysOverdue(days)
          : txt.inspection.daysLeft(days)}
      </span>
    </div>
  );
}

function FleetSection({
  title,
  icon: Icon,
  data,
  isLoading,
  isError,
}: {
  title: string;
  icon: typeof Truck;
  data?: InspectionResp;
  isLoading: boolean;
  isError: boolean;
}) {
  const { maintenancePredictionsText: txt } =
    useMaintenancePredictionsResources();
  const overdue = data?.overdue ?? [];
  const expiring = data?.expiring ?? [];
  const empty =
    !isLoading && !isError && overdue.length === 0 && expiring.length === 0;

  return (
    <Card padding="none">
      <div className="flex items-center gap-2 border-b border-border bg-elevated/50 p-4">
        <Icon className="h-5 w-5 text-secondary" />
        <h2 className="text-base font-bold text-primary">{title}</h2>
      </div>
      <div className="space-y-2 p-4">
        {isLoading && (
          <div className="flex h-24 items-center justify-center">
            <div className="h-6 w-6 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          </div>
        )}
        {isError && (
          <p className="py-6 text-center text-sm text-danger">
            {txt.inspection.loadFailed}
          </p>
        )}
        {empty && (
          <p className="flex items-center justify-center gap-2 py-6 text-center text-sm text-secondary">
            <ShieldCheck className="h-4 w-4 text-success" />
            {txt.inspection.noAlerts}
          </p>
        )}
        {overdue.length > 0 && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-danger">
              <AlertTriangle className="h-3.5 w-3.5" />
              {txt.inspection.overdue}
            </div>
            {overdue.map((it) => (
              <Row key={it.id} item={it} overdue />
            ))}
          </div>
        )}
        {expiring.length > 0 && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-warning">
              <CalendarClock className="h-3.5 w-3.5" />
              {txt.inspection.expiring}
            </div>
            {expiring.map((it) => (
              <Row key={it.id} item={it} overdue={false} />
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

export function InspectionTab() {
  const { maintenancePredictionsText: txt } =
    useMaintenancePredictionsResources();
  const vehicles = useQuery({
    queryKey: ["inspectionAlerts", "vehicles"],
    queryFn: () => fetchAlerts("/vehicles/inspection-alerts"),
  });
  const trailers = useQuery({
    queryKey: ["inspectionAlerts", "trailers"],
    queryFn: () => fetchAlerts("/trailers/inspection-alerts"),
  });

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <FleetSection
        title={txt.inspection.vehicles}
        icon={Truck}
        data={vehicles.data}
        isLoading={vehicles.isLoading}
        isError={vehicles.isError}
      />
      <FleetSection
        title={txt.inspection.trailers}
        icon={Truck}
        data={trailers.data}
        isLoading={trailers.isLoading}
        isError={trailers.isError}
      />
    </div>
  );
}
