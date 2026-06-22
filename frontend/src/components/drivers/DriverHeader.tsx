import { Plus } from "lucide-react";
import { Button } from "../ui/Button";
import { DataExportImport } from "../shared/DataExportImport";
import { driverHeaderText } from "../../resources/tr/drivers";

interface DriverHeaderProps {
  onAdd: () => void;
  onExport: () => Promise<void>;
  onDownloadTemplate: () => Promise<void>;
  onImport: (file: File) => Promise<void>;
}

export function DriverHeader({
  onAdd,
  onExport,
  onDownloadTemplate,
  onImport,
}: DriverHeaderProps) {
  return (
    <div className="flex justify-end mb-8 relative z-40">
      <div className="flex items-center gap-3">
        <DataExportImport
          variant="toolbar"
          onExport={onExport}
          onDownloadTemplate={onDownloadTemplate}
          onImport={onImport}
        />
        <Button onClick={onAdd} variant="primary" className="px-6 h-10 text-sm">
          <Plus className="w-5 h-5" /> {driverHeaderText.addButton}
        </Button>
      </div>
    </div>
  );
}
