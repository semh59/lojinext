import { useState, useRef, useEffect } from "react";
import {
  FileSpreadsheet,
  Download,
  Upload,
  RefreshCw,
  ChevronDown,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "../ui/Button";
import { cn } from "../../lib/utils";
import { ExcelUploadModal } from "./ExcelUploadModal";
import { RequirePermission } from "../auth/RequirePermission";
import { useSharedResources } from "../../resources/useResources";
interface DataExportImportProps {
  onExport?: () => Promise<void>;
  onImport?: (file: File) => Promise<any>;
  onImportSuccess?: () => void;
  onDownloadTemplate?: () => Promise<void>;
  variant?: "toolbar" | "dropdown";
  className?: string;
}

export function DataExportImport({
  onExport,
  onImport,
  onImportSuccess,
  onDownloadTemplate,
  variant = "toolbar",
  className,
}: DataExportImportProps) {
  const { dataTransferText } = useSharedResources();
  const [isExporting, setIsExporting] = useState(false);
  const [isTemplateDownloading, setIsTemplateDownloading] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleExport = async () => {
    if (!onExport) return;
    setIsExporting(true);
    try {
      await onExport();
    } finally {
      setIsExporting(false);
    }
  };

  const processFile = async (file: File) => {
    if (!onImport) return;

    const allowedExtensions = [".xlsx", ".xls"];
    const fileName = file.name.toLowerCase();
    if (!allowedExtensions.some((ext) => fileName.endsWith(ext))) {
      return;
    }

    const result = await onImport(file);
    if (onImportSuccess) {
      onImportSuccess();
    }
    return result;
  };

  const handleDownloadTemplate = async () => {
    if (!onDownloadTemplate) return;
    setIsTemplateDownloading(true);
    try {
      await onDownloadTemplate();
    } finally {
      setIsTemplateDownloading(false);
    }
  };

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      {variant === "toolbar" ? (
        <Button
          variant="secondary"
          onClick={() => setIsMenuOpen(!isMenuOpen)}
          className={cn(
            "h-[32px] px-3 font-bold shadow-none",
            isMenuOpen && "border-accent text-accent",
          )}
        >
          <ChevronDown
            className={cn(
              "w-3.5 h-3.5 transition-transform",
              isMenuOpen && "rotate-180",
            )}
          />
          {dataTransferText.toolbarButton}
        </Button>
      ) : null}

      <AnimatePresence>
        {(variant === "dropdown" || isMenuOpen) && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            className={cn(
              "bg-surface border border-border shadow-2xl overflow-hidden min-w-[260px] z-[100] rounded-2xl",
              variant === "toolbar"
                ? "absolute right-0 top-full mt-2"
                : "w-full",
            )}
          >
            {onImport && (
              <RequirePermission permission="sefer:write">
                <button
                  onClick={() => {
                    setIsUploadModalOpen(true);
                    setIsMenuOpen(false);
                  }}
                  className="w-full px-5 py-3 text-left hover:bg-elevated flex items-center gap-4 transition-all group border-b border-border"
                >
                  <div className="w-10 h-10 rounded-lg bg-info/10 flex items-center justify-center text-info group-hover:bg-info group-hover:text-bg-base transition-all transform group-hover:scale-110">
                    <Upload className="w-5 h-5" />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-sm font-bold text-primary tracking-tight">
                      {dataTransferText.uploadActionTitle}
                    </span>
                    <span className="text-[10px] text-secondary font-bold uppercase tracking-wider">
                      {dataTransferText.uploadActionDescription}
                    </span>
                  </div>
                </button>
              </RequirePermission>
            )}

            {onDownloadTemplate && (
              <button
                onClick={() => {
                  handleDownloadTemplate();
                  setIsMenuOpen(false);
                }}
                disabled={isTemplateDownloading}
                className="w-full px-5 py-3 text-left hover:bg-elevated flex items-center gap-4 transition-all group border-b border-border disabled:opacity-50"
              >
                <div className="w-10 h-10 rounded-lg bg-success/10 flex items-center justify-center text-success group-hover:bg-success group-hover:text-bg-base transition-all transform group-hover:scale-110">
                  {isTemplateDownloading ? (
                    <RefreshCw className="w-5 h-5 animate-spin" />
                  ) : (
                    <FileSpreadsheet className="w-5 h-5" />
                  )}
                </div>
                <div className="flex flex-col">
                  <span className="text-sm font-bold text-primary tracking-tight">
                    {dataTransferText.templateActionTitle}
                  </span>
                  <span className="text-[10px] text-secondary font-bold uppercase tracking-wider">
                    {dataTransferText.templateActionDescription}
                  </span>
                </div>
              </button>
            )}

            {onExport && (
              <button
                onClick={() => {
                  handleExport();
                  setIsMenuOpen(false);
                }}
                disabled={isExporting}
                className="w-full px-5 py-4 text-left hover:bg-elevated flex items-center gap-4 transition-all group disabled:opacity-50"
              >
                <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center text-accent group-hover:bg-accent group-hover:text-bg-base transition-all transform group-hover:scale-110">
                  {isExporting ? (
                    <RefreshCw className="w-5 h-5 animate-spin" />
                  ) : (
                    <Download className="w-5 h-5" />
                  )}
                </div>
                <div className="flex flex-col">
                  <span className="text-sm font-bold text-primary tracking-tight">
                    {dataTransferText.exportActionTitle}
                  </span>
                  <span className="text-[10px] text-secondary font-bold uppercase tracking-wider">
                    {dataTransferText.exportActionDescription}
                  </span>
                </div>
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <ExcelUploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUpload={processFile}
      />
    </div>
  );
}
