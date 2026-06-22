import { Plus } from "lucide-react";
import { Button } from "../ui/Button";
import { DataExportImport } from "../shared/DataExportImport";
import { useVehiclesResources } from "../../resources/useResources";
interface VehicleHeaderProps {
  onAdd: () => void;
  onExport: () => Promise<void>;
  onDownloadTemplate: () => Promise<void>;
  onImport: (file: File) => Promise<void>;
}

export function VehicleHeader({
  onAdd,
  onExport,
  onDownloadTemplate,
  onImport,
}: VehicleHeaderProps) {
  const { vehicleHeaderText } = useVehiclesResources();
  return (
    <div className="flex justify-end gap-6 relative z-40">
      <div className="flex flex-wrap items-center gap-3">
        <DataExportImport
          onExport={onExport}
          onDownloadTemplate={onDownloadTemplate}
          onImport={onImport}
        />
        <Button onClick={onAdd} variant="primary" className="gap-2">
          <Plus className="w-4 h-4" /> {vehicleHeaderText.addButton}
        </Button>
      </div>
    </div>
  );
}
