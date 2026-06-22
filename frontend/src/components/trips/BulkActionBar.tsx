import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle, Trash2, X, XCircle } from "lucide-react";

import { tripBulkActionText, tripModuleText } from "../../resources/tr/trips";
import { RequirePermission } from "../auth/RequirePermission";
import { Button } from "../ui/Button";

interface BulkActionBarProps {
  selectedCount: number;
  onClear: () => void;
  onStatusUpdate: () => void;
  onCancel: () => void;
  onDelete: () => void;
  onApprove?: () => void;
  isApproving?: boolean;
}

export function BulkActionBar({
  selectedCount,
  onClear,
  onStatusUpdate,
  onCancel,
  onDelete,
  onApprove,
  isApproving,
}: BulkActionBarProps) {
  if (selectedCount === 0) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ y: 100, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 100, opacity: 0 }}
        className="fixed bottom-8 left-1/2 z-[100] w-full max-w-2xl -translate-x-1/2 px-4"
      >
        <div className="flex items-center justify-between gap-6 rounded-[24px] border border-accent/40 bg-surface/90 p-4 shadow-2xl backdrop-blur-xl">
          <div className="flex items-center gap-4">
            <button
              onClick={onClear}
              className="rounded-full p-2 text-secondary transition-colors hover:bg-elevated hover:text-primary"
            >
              <X className="h-5 w-5" />
            </button>
            <div className="flex flex-col">
              <span className="text-lg font-black leading-none text-accent">
                {selectedCount}
              </span>
              <span className="text-[10px] font-bold uppercase tracking-wider text-secondary">
                {tripBulkActionText.selectedTrips}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <RequirePermission permission="sefer:onayla">
              {onApprove && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onApprove}
                  isLoading={isApproving}
                  className="gap-2 rounded-xl border-success/30 text-success hover:border-success/60 hover:bg-success/10"
                >
                  <CheckCircle className="h-4 w-4" />
                  {tripModuleText.bulkApprove}
                </Button>
              )}
            </RequirePermission>
            <RequirePermission permission="sefer:write">
              <Button
                variant="outline"
                size="sm"
                onClick={onStatusUpdate}
                className="gap-2 rounded-xl border-border text-secondary hover:border-accent/50 hover:text-accent"
              >
                <CheckCircle className="h-4 w-4" />
                {tripBulkActionText.updateStatus}
              </Button>
            </RequirePermission>

            <RequirePermission permission="sefer:write">
              <Button
                variant="outline"
                size="sm"
                onClick={onCancel}
                className="gap-2 rounded-xl border-danger/20 text-secondary hover:border-danger/50 hover:text-danger"
              >
                <XCircle className="h-4 w-4" />
                {tripBulkActionText.cancel}
              </Button>
            </RequirePermission>

            <RequirePermission permission="sefer:delete">
              <Button
                variant="secondary"
                size="sm"
                onClick={onDelete}
                className="gap-2 rounded-xl border-none bg-danger/10 text-danger hover:bg-danger/20"
              >
                <Trash2 className="h-4 w-4" />
                {tripBulkActionText.bulkDelete}
              </Button>
            </RequirePermission>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
