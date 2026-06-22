import React from "react";
import { AlertTriangle, XCircle } from "lucide-react";

import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { useTripsResources } from "../../resources/useResources";

interface BulkCancelModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
  selectedCount: number;
  isSubmitting: boolean;
}

export function BulkCancelModal({
  isOpen,
  onClose,
  onConfirm,
  selectedCount,
  isSubmitting,
}: BulkCancelModalProps) {
  const { tripBulkCancelModalText } = useTripsResources();
  const [reason, setReason] = React.useState("");

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={tripBulkCancelModalText.title}
      size="md"
    >
      <div className="space-y-6 py-2">
        <div className="flex items-center gap-4 rounded-2xl border border-danger/20 bg-danger/10 p-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-danger/20">
            <XCircle className="h-6 w-6 text-danger" />
          </div>
          <div>
            <h4 className="font-bold text-primary">
              {tripBulkCancelModalText.summary(selectedCount)}
            </h4>
            <p className="text-xs text-secondary">
              {tripBulkCancelModalText.description}
            </p>
          </div>
        </div>

        <div className="space-y-2">
          <label className="ml-1 text-xs font-bold uppercase tracking-widest text-secondary">
            {tripBulkCancelModalText.reasonLabel}
          </label>
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder={tripBulkCancelModalText.reasonPlaceholder}
            className="h-32 w-full resize-none rounded-xl border border-border bg-elevated/10 p-4 font-medium text-primary outline-none transition-all placeholder:text-secondary/40 focus:ring-2 focus:ring-danger/50"
          />
          <div className="ml-1 flex items-center gap-2 text-danger/70">
            <AlertTriangle className="h-3.5 w-3.5" />
            <span className="text-[10px] font-bold italic">
              {tripBulkCancelModalText.reasonHint}
            </span>
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t border-border pt-4">
          <Button variant="ghost" onClick={onClose} disabled={isSubmitting}>
            {tripBulkCancelModalText.cancel}
          </Button>
          <Button
            variant="primary"
            onClick={() => onConfirm(reason)}
            isLoading={isSubmitting}
            disabled={reason.length < 5}
            className="border-none bg-danger px-8 shadow-[0_4px_20px_rgba(239,68,68,0.3)] shadow-danger/20 hover:bg-danger/80"
          >
            {tripBulkCancelModalText.confirm}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
