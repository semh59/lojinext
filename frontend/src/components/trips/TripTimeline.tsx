import React from "react";
import { format } from "date-fns";
import { tr } from "date-fns/locale";
import {
  Activity,
  Clock,
  FileEdit,
  Gauge,
  PlusCircle,
  RefreshCw,
  Trash2,
  User,
} from "lucide-react";

import { tripTimelineText } from "../../resources/tr/trips";
import { SeferTimelineItem } from "../../types";

interface TripTimelineProps {
  items: SeferTimelineItem[];
  isLoading?: boolean;
}

const EVENT_LABELS: Record<SeferTimelineItem["tip"], string> = {
  CREATE: tripTimelineText.eventLabels.CREATE,
  UPDATE: tripTimelineText.eventLabels.UPDATE,
  STATUS_CHANGE: tripTimelineText.eventLabels.STATUS_CHANGE,
  PREDICTION_REFRESH: tripTimelineText.eventLabels.PREDICTION_REFRESH,
  RECONCILIATION: tripTimelineText.eventLabels.RECONCILIATION,
  DELETE: tripTimelineText.eventLabels.DELETE,
};

const getEventIcon = (eventType: SeferTimelineItem["tip"]) => {
  switch (eventType) {
    case "CREATE":
      return <PlusCircle className="h-4 w-4 text-success" />;
    case "DELETE":
      return <Trash2 className="h-4 w-4 text-danger" />;
    case "STATUS_CHANGE":
      return <Activity className="h-4 w-4 text-warning" />;
    case "PREDICTION_REFRESH":
      return <Gauge className="h-4 w-4 text-accent" />;
    case "RECONCILIATION":
      return <RefreshCw className="h-4 w-4 text-accent" />;
    default:
      return <FileEdit className="h-4 w-4 text-secondary" />;
  }
};

const renderValue = (value: unknown) => {
  if (value === null || value === undefined) return "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
};

export const TripTimeline: React.FC<TripTimelineProps> = ({
  items,
  isLoading,
}) => {
  if (isLoading) {
    return (
      <div className="flex flex-col gap-6 py-4">
        {[...Array(3)].map((_, index) => (
          <div key={index} className="flex animate-pulse gap-4">
            <div className="h-8 w-8 rounded-full bg-elevated/5" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-1/3 rounded bg-elevated/10" />
              <div className="h-3 w-2/3 rounded bg-elevated/5" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!items?.length) {
    return (
      <div className="py-10 text-center text-secondary">
        <Clock className="mx-auto mb-3 h-10 w-10 opacity-20" />
        <p className="text-sm font-medium">{tripTimelineText.empty}</p>
      </div>
    );
  }

  return (
    <div className="relative space-y-8 before:absolute before:inset-0 before:ml-4 before:h-full before:w-0.5 before:-translate-x-px before:bg-gradient-to-b before:from-transparent before:via-border before:to-transparent">
      {items.map((item) => (
        <div key={item.id} className="group relative flex items-start gap-4">
          <div className="relative z-10 flex h-8 w-8 items-center justify-center rounded-full border border-border bg-surface shadow-xl transition-colors group-hover:border-accent/50">
            {getEventIcon(item.tip)}
          </div>

          <div className="flex min-w-0 flex-1 flex-col gap-2">
            <div className="flex items-center justify-between gap-4">
              <span className="truncate text-xs font-black uppercase tracking-tight text-primary">
                {EVENT_LABELS[item.tip]}
              </span>
              <span className="whitespace-nowrap text-[10px] font-bold text-secondary">
                {format(new Date(item.zaman), "HH:mm (d MMM yyyy)", {
                  locale: tr,
                })}
              </span>
            </div>

            <p className="text-xs font-medium leading-relaxed text-secondary">
              {item.ozet}
            </p>

            <div className="mt-1 flex items-center gap-2">
              <div className="flex items-center gap-1.5 rounded-full border border-border bg-elevated/5 px-2 py-0.5">
                <User className="h-3 w-3 text-secondary" />
                <span className="text-[10px] font-bold text-secondary">
                  {item.kullanici}
                </span>
              </div>

              {(item.changes?.length ?? 0) > 0 && (
                <div className="flex flex-wrap gap-1">
                  {(item.changes || []).slice(0, 4).map((change: any) => (
                    <span
                      key={`${item.id}-${change.alan}`}
                      className="rounded bg-accent/10 px-1.5 py-0.5 text-[9px] font-bold uppercase text-accent"
                    >
                      {change.alan}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {(item.prediction ||
              item.technical_details ||
              (item.changes?.length ?? 0) > 0) && (
              <details className="group/details mt-2">
                <summary className="cursor-pointer text-[10px] font-bold uppercase tracking-wider text-secondary hover:text-primary">
                  {tripTimelineText.technicalDetails}
                </summary>
                <div className="mt-2 space-y-3 rounded-xl border border-border bg-elevated/20 p-3">
                  {item.prediction && (
                    <div className="space-y-1">
                      <div className="text-[10px] font-black uppercase tracking-wider text-accent">
                        {tripTimelineText.predictionInfo}
                      </div>
                      <div className="text-[11px] text-secondary">
                        {item.prediction.onceki_tahmini_tuketim ?? "-"} {" -> "}{" "}
                        {item.prediction.tahmini_tuketim ?? "-"} L/100km
                      </div>
                      {item.prediction.tahmin_meta && (
                        <div className="grid grid-cols-1 gap-2 text-[11px] md:grid-cols-2">
                          <div className="text-secondary">
                            {tripTimelineText.model}:{" "}
                            <span className="text-primary">
                              {item.prediction.tahmin_meta.model_used ?? "-"}
                            </span>
                          </div>
                          <div className="text-secondary">
                            {tripTimelineText.version}:{" "}
                            <span className="text-primary">
                              {item.prediction.tahmin_meta.model_version ?? "-"}
                            </span>
                          </div>
                          <div className="text-secondary">
                            {tripTimelineText.confidence}:{" "}
                            <span className="text-primary">
                              {item.prediction.tahmin_meta.confidence_score ??
                                "-"}
                            </span>
                          </div>
                          <div className="text-secondary">
                            {tripTimelineText.fallback}:{" "}
                            <span className="text-primary">
                              {item.prediction.tahmin_meta.fallback_triggered
                                ? tripTimelineText.yes
                                : tripTimelineText.no}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {(item.changes?.length ?? 0) > 0 && (
                    <div className="space-y-1">
                      <div className="text-[10px] font-black uppercase tracking-wider text-accent">
                        {tripTimelineText.fieldChanges}
                      </div>
                      <div className="custom-scrollbar max-h-40 space-y-1 overflow-y-auto">
                        {(item.changes || []).map(
                          (change: any, index: number) => (
                            <div
                              key={`${item.id}-change-${index}`}
                              className="text-[11px] text-secondary"
                            >
                              <span className="font-semibold text-primary">
                                {change.alan}:
                              </span>{" "}
                              {renderValue(change.eski)} {" -> "}{" "}
                              {renderValue(change.yeni)}
                            </div>
                          ),
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </details>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};
