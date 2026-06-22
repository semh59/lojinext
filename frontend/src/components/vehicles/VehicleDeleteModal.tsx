import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Trash2 } from "lucide-react";

import { Vehicle } from "../../types";
import { vehicleDeleteText } from "../../resources/tr/vehicles";
import { Button } from "../ui/Button";

interface VehicleDeleteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  vehicle: Vehicle | null;
}

export function VehicleDeleteModal({
  isOpen,
  onClose,
  onConfirm,
  vehicle,
}: VehicleDeleteModalProps) {
  if (!isOpen || !vehicle) {
    return null;
  }

  const isSoftDelete = vehicle.aktif;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[60] flex items-center justify-center bg-base/20 p-4 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="w-full max-w-md overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl"
        >
          <div className="p-8 text-center">
            <div
              className={`mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-2xl ${
                isSoftDelete
                  ? "bg-warning/10 text-warning"
                  : "bg-danger/10 text-danger"
              }`}
            >
              {isSoftDelete ? (
                <AlertTriangle className="h-10 w-10" />
              ) : (
                <Trash2 className="h-10 w-10" />
              )}
            </div>

            <h2 className="mb-2 text-2xl font-black text-primary">
              {isSoftDelete
                ? vehicleDeleteText.title.soft
                : vehicleDeleteText.title.hard}
            </h2>

            <p className="mb-8 font-medium leading-relaxed text-secondary">
              {isSoftDelete
                ? vehicleDeleteText.description.soft(vehicle.plaka)
                : vehicleDeleteText.description.hard(vehicle.plaka)}
            </p>

            <div className="flex gap-3">
              <Button
                variant="secondary"
                onClick={onClose}
                className="h-12 flex-1 text-base"
              >
                {vehicleDeleteText.actions.cancel}
              </Button>
              <Button
                variant="danger"
                onClick={async () => {
                  await onConfirm();
                  onClose();
                }}
                className={`h-12 flex-1 text-base ${
                  isSoftDelete
                    ? "bg-warning text-bg-base hover:bg-warning/80"
                    : ""
                }`}
              >
                {isSoftDelete
                  ? vehicleDeleteText.actions.softConfirm
                  : vehicleDeleteText.actions.hardConfirm}
              </Button>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
