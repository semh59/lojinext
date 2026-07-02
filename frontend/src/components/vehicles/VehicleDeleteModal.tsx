import { Vehicle } from "../../types";
import { DeleteConfirmModal } from "../ui/DeleteConfirmModal";
import { useVehiclesResources } from "../../resources/useResources";

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
  const { vehicleDeleteText } = useVehiclesResources();
  if (!isOpen || !vehicle) {
    return null;
  }

  const isSoftDelete = vehicle.aktif;

  return (
    <DeleteConfirmModal
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={async () => {
        await onConfirm();
        onClose();
      }}
      variant={isSoftDelete ? "warning" : "danger"}
      title={
        isSoftDelete
          ? vehicleDeleteText.title.soft
          : vehicleDeleteText.title.hard
      }
      description={
        isSoftDelete
          ? vehicleDeleteText.description.soft(vehicle.plaka)
          : vehicleDeleteText.description.hard(vehicle.plaka)
      }
      confirmLabel={
        isSoftDelete
          ? vehicleDeleteText.actions.softConfirm
          : vehicleDeleteText.actions.hardConfirm
      }
      cancelLabel={vehicleDeleteText.actions.cancel}
    />
  );
}
