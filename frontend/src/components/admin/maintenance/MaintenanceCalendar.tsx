import { useMemo, useState } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import type { EventClickArg, EventInput } from "@fullcalendar/core";
import { AlertCircle, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { useMaintenancePredictions } from "@/hooks/useMaintenancePredictions";
import type {
  MaintenancePrediction,
  RiskLevel,
} from "@/api/maintenance-predictions";
import { MaintenanceDetailDrawer } from "./MaintenanceDetailDrawer";
import { useMaintenancePredictionsResources } from "@/resources/useResources";

const RISK_COLOR: Record<RiskLevel, string> = {
  overdue: "#dc2626", // red-600
  soon: "#f59e0b", // amber-500
  normal: "#3b82f6", // blue-500
  low: "#10b981", // emerald-500
};

function predictionToEvent(p: MaintenancePrediction): EventInput | null {
  if (!p.predictable || !p.predicted_date) return null;
  return {
    id: `${p.arac_id}:${p.bakim_tipi}`,
    title: `${p.plaka} — ${p.bakim_tipi}`,
    start: p.predicted_date,
    allDay: true,
    backgroundColor: RISK_COLOR[(p.risk_level ?? "low") as RiskLevel],
    borderColor: RISK_COLOR[(p.risk_level ?? "low") as RiskLevel],
    textColor: "white",
    extendedProps: { prediction: p },
  };
}

export function MaintenanceCalendar() {
  const { maintenancePredictionsText } = useMaintenancePredictionsResources();
  const { data, isLoading, error } = useMaintenancePredictions();
  const [selected, setSelected] = useState<MaintenancePrediction | null>(null);

  const events = useMemo<EventInput[]>(() => {
    if (!data) return [];
    return data
      .map(predictionToEvent)
      .filter((e): e is EventInput => e !== null);
  }, [data]);

  const handleEventClick = (arg: EventClickArg) => {
    const pred = arg.event.extendedProps?.prediction as
      | MaintenancePrediction
      | undefined;
    if (pred) setSelected(pred);
  };

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-12 text-secondary">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="text-sm">Yükleniyor…</span>
      </div>
    );
  }

  if (error) {
    const status = (error as { response?: { status?: number } })?.response
      ?.status;
    const msg =
      status === 503
        ? maintenancePredictionsText.errors.flagOff
        : status === 403
          ? maintenancePredictionsText.errors.forbidden
          : maintenancePredictionsText.errors.loadFailed;
    return (
      <div className="flex items-center gap-2 rounded-card border border-danger/30 bg-danger/5 px-3 py-3 text-sm text-danger">
        <AlertCircle className="h-4 w-4 shrink-0" />
        {msg}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <Legend />
      <div className="rounded-modal border border-border bg-surface p-4 shadow-sm">
        <FullCalendar
          plugins={[dayGridPlugin]}
          initialView="dayGridMonth"
          headerToolbar={{
            left: "prev,next today",
            center: "title",
            right: "dayGridMonth",
          }}
          events={events}
          eventClick={handleEventClick}
          height="auto"
          locale="tr"
          firstDay={1}
          buttonText={{ today: "Bugün" }}
        />
      </div>
      <MaintenanceDetailDrawer
        prediction={selected}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}

function Legend() {
  const { maintenancePredictionsText } = useMaintenancePredictionsResources();
  const items: Array<{ key: RiskLevel; color: string }> = [
    { key: "overdue", color: RISK_COLOR.overdue },
    { key: "soon", color: RISK_COLOR.soon },
    { key: "normal", color: RISK_COLOR.normal },
    { key: "low", color: RISK_COLOR.low },
  ];
  return (
    <div className="flex flex-wrap items-center gap-3 text-[11px] text-secondary">
      {items.map((i) => (
        <span key={i.key} className="inline-flex items-center gap-1.5">
          <span
            className={cn("h-2 w-2 rounded-full")}
            style={{ backgroundColor: i.color }}
          />
          {maintenancePredictionsText.calendarLegend[i.key]}
        </span>
      ))}
    </div>
  );
}
