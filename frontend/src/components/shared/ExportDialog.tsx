import React, { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  Calendar,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  FileText,
  Loader2,
  Truck,
  X,
} from "lucide-react";

import { vehiclesApi } from "../../services/api";
import { cn } from "../../lib/utils";
import { Button } from "../ui/Button";
import { useReportsResources } from "../../resources/useResources";
import { useLocale } from "../../hooks/useLocale";

export type ExportType =
  | "fleet_summary"
  | "vehicle_report"
  | "driver_comparison"
  | "cost_trend"
  | "trip_list"
  | "fuel_list"
  | "location_list"
  | "driver_list"
  | "vehicle_list";

export interface ExportConfig {
  format: "pdf" | "excel";
  startDate?: string;
  endDate?: string;
  targetId?: string | number;
  month?: number;
  year?: number;
}

export interface ExportDialogProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description: string;
  type: ExportType;
  onExport: (config: ExportConfig) => Promise<void>;
}

type VehicleOption = {
  id: number | string;
  plaka?: string | null;
  marka?: string | null;
  model?: string | null;
};

export function ExportDialog({
  isOpen,
  onClose,
  title,
  description,
  type,
  onExport,
}: ExportDialogProps) {
  const { reportExportDialogText } = useReportsResources();
  const locale = useLocale();
  const [format, setFormat] = useState<"pdf" | "excel">("pdf");
  const [startDate, setStartDate] = useState(
    new Date(new Date().setDate(new Date().getDate() - 30))
      .toISOString()
      .split("T")[0],
  );
  const [endDate, setEndDate] = useState(
    new Date().toISOString().split("T")[0],
  );
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [year, setYear] = useState(new Date().getFullYear());
  const [selectedVehicleId, setSelectedVehicleId] = useState("");
  const [vehicles, setVehicles] = useState<VehicleOption[]>([]);
  const [isLoadingVehicles, setIsLoadingVehicles] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => {
    if (!isOpen || type !== "vehicle_report") {
      return;
    }

    setIsLoadingVehicles(true);
    vehiclesApi
      .getAll({ limit: 100 })
      .then((data) => {
        const items = Array.isArray(data) ? data : data.items || [];
        const normalizedVehicles = items.filter(
          (vehicle): vehicle is VehicleOption =>
            vehicle?.id !== undefined && vehicle?.id !== null,
        );
        setVehicles(normalizedVehicles);
        if (normalizedVehicles.length > 0) {
          setSelectedVehicleId(String(normalizedVehicles[0].id));
        }
      })
      .catch((requestError) => {
        console.error("Vehicle export options failed to load:", requestError);
        setError(reportExportDialogText.vehicleLoadError);
      })
      .finally(() => setIsLoadingVehicles(false));
  }, [isOpen, type, reportExportDialogText.vehicleLoadError]);

  const isPdfSupported = ![
    "location_list",
    "driver_list",
    "vehicle_list",
    "fuel_list",
    "trip_list",
  ].includes(type);

  const handleExport = async () => {
    setIsExporting(true);
    setError(null);

    try {
      if (type === "vehicle_report" && !selectedVehicleId) {
        setError(reportExportDialogText.selectVehicleError);
        return;
      }

      await onExport({
        format,
        startDate,
        endDate,
        targetId: selectedVehicleId,
        month,
        year,
      });

      setIsSuccess(true);
      setTimeout(() => {
        setIsSuccess(false);
        onClose();
      }, 2000);
    } catch (requestError) {
      console.error("Export dialog request failed:", requestError);
      setError(reportExportDialogText.exportError);
    } finally {
      setIsExporting(false);
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
      />

      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-border bg-elevated shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-border bg-elevated/30 px-6 py-4">
          <div>
            <h3 className="text-lg font-bold text-primary">{title}</h3>
            <p className="mt-0.5 text-xs text-secondary">{description}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-2 text-secondary transition-colors hover:bg-elevated hover:text-primary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-6 p-6">
          <div className="space-y-3">
            <label className="text-sm font-bold uppercase tracking-wider text-secondary">
              {reportExportDialogText.fileFormat}
            </label>
            <div className="grid grid-cols-2 gap-4">
              <button
                onClick={() => isPdfSupported && setFormat("pdf")}
                disabled={!isPdfSupported}
                className={cn(
                  "group flex flex-col items-center gap-3 rounded-xl border-2 p-4 transition-all",
                  format === "pdf"
                    ? "border-accent bg-accent/5"
                    : "border-border bg-elevated/50 hover:border-border-hover",
                  !isPdfSupported && "cursor-not-allowed opacity-50 grayscale",
                )}
              >
                <div
                  className={cn(
                    "rounded-lg p-3 transition-colors",
                    format === "pdf"
                      ? "bg-accent text-white"
                      : "bg-elevated text-secondary group-hover:text-primary",
                  )}
                >
                  <FileText className="h-6 w-6" />
                </div>
                <div className="text-center">
                  <span className="block font-bold text-primary">
                    {reportExportDialogText.pdfLabel}
                  </span>
                  <span className="text-[11px] text-secondary">
                    {reportExportDialogText.pdfDescription}
                  </span>
                </div>
              </button>

              <button
                onClick={() => setFormat("excel")}
                className={cn(
                  "group flex flex-col items-center gap-3 rounded-xl border-2 p-4 transition-all",
                  format === "excel"
                    ? "border-green-500 bg-green-500/5"
                    : "border-border bg-elevated/50 hover:border-border-hover",
                )}
              >
                <div
                  className={cn(
                    "rounded-lg p-3 transition-colors",
                    format === "excel"
                      ? "bg-green-500 text-white"
                      : "bg-elevated text-secondary group-hover:text-primary",
                  )}
                >
                  <FileSpreadsheet className="h-6 w-6" />
                </div>
                <div className="text-center">
                  <span className="block font-bold text-primary">
                    {reportExportDialogText.excelLabel}
                  </span>
                  <span className="text-[11px] text-secondary">
                    {reportExportDialogText.excelDescription}
                  </span>
                </div>
              </button>
            </div>
          </div>

          <div className="space-y-4 pt-2">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-xs font-bold text-secondary">
                  <Calendar className="h-3.5 w-3.5" />
                  {reportExportDialogText.startDate.toUpperCase()}
                </label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(event) => setStartDate(event.target.value)}
                  className="w-full rounded-lg border border-border bg-elevated px-3 py-2 text-sm text-primary outline-none focus:border-accent"
                />
              </div>
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-xs font-bold text-secondary">
                  <Calendar className="h-3.5 w-3.5" />
                  {reportExportDialogText.endDate.toUpperCase()}
                </label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(event) => setEndDate(event.target.value)}
                  className="w-full rounded-lg border border-border bg-elevated px-3 py-2 text-sm text-primary outline-none focus:border-accent"
                />
              </div>
            </div>

            {type === "vehicle_report" && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="flex items-center gap-2 text-xs font-bold text-secondary">
                    <Truck className="h-3.5 w-3.5" />
                    {reportExportDialogText.vehicleSelection.toUpperCase()}
                  </label>
                  <select
                    value={selectedVehicleId}
                    onChange={(event) =>
                      setSelectedVehicleId(event.target.value)
                    }
                    disabled={isLoadingVehicles}
                    className="w-full rounded-lg border border-border bg-elevated px-3 py-2 text-sm text-primary outline-none focus:border-accent"
                  >
                    {isLoadingVehicles ? (
                      <option>{reportExportDialogText.vehiclesLoading}</option>
                    ) : vehicles.length === 0 ? (
                      <option>{reportExportDialogText.vehicleNotFound}</option>
                    ) : (
                      vehicles.map((vehicle) => (
                        <option key={vehicle.id} value={vehicle.id}>
                          {vehicle.plaka} - {vehicle.marka} {vehicle.model}
                        </option>
                      ))
                    )}
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="flex items-center gap-2 text-xs font-bold text-secondary">
                      <Calendar className="h-3.5 w-3.5" />
                      {reportExportDialogText.month.toUpperCase()}
                    </label>
                    <select
                      value={month}
                      onChange={(event) => setMonth(Number(event.target.value))}
                      className="w-full rounded-lg border border-border bg-elevated px-3 py-2 text-sm text-primary outline-none focus:border-accent"
                    >
                      {Array.from({ length: 12 }, (_, index) => index + 1).map(
                        (calendarMonth) => (
                          <option key={calendarMonth} value={calendarMonth}>
                            {new Date(2000, calendarMonth - 1).toLocaleString(
                              locale,
                              {
                                month: "long",
                              },
                            )}
                          </option>
                        ),
                      )}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="flex items-center gap-2 text-xs font-bold text-secondary">
                      <Calendar className="h-3.5 w-3.5" />
                      {reportExportDialogText.year.toUpperCase()}
                    </label>
                    <select
                      value={year}
                      onChange={(event) => setYear(Number(event.target.value))}
                      className="w-full rounded-lg border border-border bg-elevated px-3 py-2 text-sm text-primary outline-none focus:border-accent"
                    >
                      {[2023, 2024, 2025, 2026].map((optionYear) => (
                        <option key={optionYear} value={optionYear}>
                          {optionYear}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            )}
          </div>

          {error && (
            <div className="flex items-center gap-3 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-500">
              <AlertCircle className="h-5 w-5 flex-shrink-0" />
              {error}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 border-t border-border bg-elevated/30 px-6 py-4">
          <Button variant="ghost" onClick={onClose} disabled={isExporting}>
            {reportExportDialogText.cancel}
          </Button>
          <Button
            onClick={handleExport}
            disabled={isExporting || isSuccess}
            className={cn(
              "relative min-w-[140px] overflow-hidden transition-all",
              isSuccess && "border-none bg-green-600 hover:bg-green-600",
              format === "excel" &&
                !isSuccess &&
                "bg-green-500 text-white hover:bg-green-600",
            )}
          >
            <AnimatePresence mode="wait">
              {isExporting ? (
                <motion.div
                  key="loading"
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="flex items-center justify-center gap-2"
                >
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>{reportExportDialogText.preparing}</span>
                </motion.div>
              ) : isSuccess ? (
                <motion.div
                  key="success"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center justify-center gap-2"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  <span>{reportExportDialogText.downloaded}</span>
                </motion.div>
              ) : (
                <motion.div
                  key="idle"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center justify-center gap-2"
                >
                  <Download className="h-4 w-4" />
                  <span>
                    {format === "pdf"
                      ? reportExportDialogText.downloadPdf
                      : reportExportDialogText.downloadExcel}
                  </span>
                </motion.div>
              )}
            </AnimatePresence>
          </Button>
        </div>
      </motion.div>
    </div>
  );
}
