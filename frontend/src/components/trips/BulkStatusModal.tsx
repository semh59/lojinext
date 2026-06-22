import React from "react";
import { Clock } from "lucide-react";

import {
  TRIP_STATUS_PLANLANDI,
  TRIP_STATUS_TAMAMLANDI,
  type TripAssignableStatus,
} from "../../lib/trip-status";
import { cn } from "../../lib/utils";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { useTripsResources } from "../../resources/useResources";

interface BulkStatusModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (status: TripAssignableStatus) => void;
  selectedCount: number;
  isSubmitting: boolean;
}

export function BulkStatusModal({
  isOpen,
  onClose,
  onConfirm,
  selectedCount,
  isSubmitting,
}: BulkStatusModalProps) {
  const { tripBulkStatusModalText } = useTripsResources();
  const statusOptions: Array<{
    value: TripAssignableStatus;
    label: string;
    color: string;
  }> = [
    {
      value: TRIP_STATUS_PLANLANDI as TripAssignableStatus,
      label: tripBulkStatusModalText.planned,
      color: "bg-warning",
    },
    {
      value: TRIP_STATUS_TAMAMLANDI as TripAssignableStatus,
      label: tripBulkStatusModalText.completed,
      color: "bg-success",
    },
  ];
  const [selectedStatus, setSelectedStatus] =
    React.useState<TripAssignableStatus>(
      TRIP_STATUS_TAMAMLANDI as TripAssignableStatus,
    );

  React.useEffect(() => {
    if (!isOpen) {
      setSelectedStatus(TRIP_STATUS_TAMAMLANDI as TripAssignableStatus);
    }
  }, [isOpen]);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={tripBulkStatusModalText.title}
      size="md"
    >
      <div className="space-y-6 py-2">
        <div className="flex items-center gap-4 rounded-2xl border border-border bg-elevated/20 p-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/10">
            <Clock className="h-6 w-6 text-accent" />
          </div>
          <div>
            <h4 className="font-bold text-primary">
              {tripBulkStatusModalText.selectedTrips(selectedCount)}
            </h4>
            <p className="text-xs text-secondary">
              {tripBulkStatusModalText.description}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-2">
          {statusOptions.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setSelectedStatus(option.value)}
              className={cn(
                "flex items-center gap-3 rounded-xl border p-4 text-left transition-all",
                selectedStatus === option.value
                  ? "border-accent/50 bg-elevated shadow-lg shadow-accent/5"
                  : "border-border bg-surface/50 text-secondary hover:border-accent/20",
              )}
            >
              <div className={cn("h-3 w-3 rounded-full", option.color)} />
              <span
                className={cn(
                  "font-bold",
                  selectedStatus === option.value
                    ? "text-primary"
                    : "text-secondary",
                )}
              >
                {option.label}
              </span>
            </button>
          ))}
        </div>

        <div className="rounded-xl border border-warning/20 bg-warning/5 px-4 py-3 text-xs text-secondary">
          {tripBulkStatusModalText.cancelHint}
        </div>

        <div className="flex justify-end gap-3 border-t border-border pt-4">
          <Button variant="ghost" onClick={onClose} disabled={isSubmitting}>
            {tripBulkStatusModalText.cancel}
          </Button>
          <Button
            variant="primary"
            onClick={() => onConfirm(selectedStatus)}
            isLoading={isSubmitting}
            className="px-8"
          >
            {tripBulkStatusModalText.confirm}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
