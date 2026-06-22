import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { BarChart2, FileText, PieChart, TrendingUp, X } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

import ErrorBoundary from "../components/common/ErrorBoundary";
import { CostAnalysisChart } from "../components/reports/CostAnalysisChart";
import { ReportCards } from "../components/reports/ReportCards";
import { ROICalculator } from "../components/reports/ROICalculator";
import { SavingsPotentialCard } from "../components/reports/SavingsPotentialCard";
import { PeriodCostBreakdown } from "../components/reports/PeriodCostBreakdown";
import {
  ExportConfig,
  ExportDialog,
  ExportType,
} from "../components/shared/ExportDialog";
import { useNotify } from "../context/NotificationContext";
import { cn } from "../lib/utils";
import { usePageTitle } from "../hooks/usePageTitle";
import {
  ReportDownloadOptionId,
  ReportTabId,
  reportDownloadOptions,
  reportPageText,
} from "../resources/tr/reports";
import { reportsApi } from "../services/api";

export default function ReportsPage() {
  usePageTitle("Raporlar");
  const { notify } = useNotify();
  const [activeTab, setActiveTab] = useState<ReportTabId>("pdf");
  const [isExportDialogOpen, setIsExportDialogOpen] = useState(false);
  const [exportType, setExportType] = useState<ExportType>("fleet_summary");
  const [exportTitle, setExportTitle] = useState("");
  const [exportDescription, setExportDescription] = useState("");
  const [drillDown, setDrillDown] = useState<{
    aracId: number;
    plaka: string;
  } | null>(null);

  const { data: costData = [], isLoading: costLoading } = useQuery({
    queryKey: ["costAnalysis"],
    queryFn: () => reportsApi.getCostAnalysis(),
    enabled: activeTab === "cost",
    staleTime: 10 * 60 * 1000,
  });

  const { data: vehicleComparison = [], isLoading: vehicleLoading } = useQuery({
    queryKey: ["vehicleComparison"],
    queryFn: () => reportsApi.getVehicleComparison(3),
    enabled: activeTab === "vehicle",
    staleTime: 10 * 60 * 1000,
  });

  const handleDownloadClick = async (type: ReportDownloadOptionId) => {
    const option = reportDownloadOptions[type];
    setExportType(option.exportType);
    setExportTitle(option.dialogTitle);
    setExportDescription(option.dialogDescription);
    setIsExportDialogOpen(true);
  };

  const handleExportConfirm = async (config: ExportConfig) => {
    try {
      const { format, startDate, endDate, targetId, month, year } = config;
      let blob: Blob;
      let filename = `rapor_${exportType}_${
        new Date().toISOString().split("T")[0]
      }`;

      if (format === "pdf") {
        const params: Record<string, string | number> = {};
        if (startDate) params.start_date = startDate;
        if (endDate) params.end_date = endDate;
        if (month !== undefined) params.month = month;
        if (year !== undefined) params.year = year;
        blob = await reportsApi.downloadPdf(
          exportType === "vehicle_report" ? "vehicle_detail" : exportType,
          targetId ? Number(targetId) : undefined,
          params,
        );
        filename += ".pdf";
      } else {
        const params: Record<string, string | number> = { months: 12 };
        if (startDate) params.start_date = startDate;
        if (endDate) params.end_date = endDate;
        blob = await reportsApi.downloadExcel(
          exportType === "vehicle_report" ? "fleet_summary" : exportType,
          params,
        );
        filename += ".xlsx";
      }

      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(anchor);
      notify(
        "success",
        reportPageText.exportSuccessTitle,
        reportPageText.exportSuccessMessage,
      );
    } catch (error) {
      console.error("Report export failed:", error);
      notify(
        "error",
        reportPageText.exportErrorTitle,
        reportPageText.exportErrorMessage,
      );
      throw error;
    }
  };

  const tabs: Array<{ id: ReportTabId; label: string; icon: typeof FileText }> =
    [
      { id: "pdf", label: reportPageText.tabs.pdf, icon: FileText },
      { id: "cost", label: reportPageText.tabs.cost, icon: PieChart },
      { id: "roi", label: reportPageText.tabs.roi, icon: TrendingUp },
      { id: "vehicle", label: reportPageText.tabs.vehicle, icon: BarChart2 },
    ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold text-primary">
          {reportPageText.heading}
        </h1>
        <p className="text-sm text-secondary">{reportPageText.description}</p>
      </div>

      <div className="glass flex w-fit rounded-2xl border border-border p-1.5 shadow-sm">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "relative z-10 flex items-center justify-center gap-2 rounded-xl px-6 py-2.5 text-sm font-semibold transition-all duration-200",
              activeTab === tab.id
                ? "text-white"
                : "text-tertiary hover:text-secondary",
            )}
          >
            {activeTab === tab.id && (
              <motion.div
                layoutId="reportsTabIndicator"
                className="absolute inset-0 -z-10 rounded-xl bg-accent shadow-md shadow-accent/20"
                transition={{ type: "spring", bounce: 0.15, duration: 0.4 }}
              />
            )}
            <tab.icon size={18} />
            {tab.label}
          </button>
        ))}
      </div>

      <div className="relative min-h-[500px]">
        <ErrorBoundary>
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, x: 5 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -5 }}
              transition={{ duration: 0.25, ease: "easeOut" }}
              className="glass rounded-2xl border border-border p-6 shadow-sm"
            >
              {activeTab === "pdf" && (
                <ReportCards onDownload={handleDownloadClick} />
              )}
              {activeTab === "cost" && (
                <div className="space-y-6">
                  {costLoading ? (
                    <div className="flex h-64 items-center justify-center text-secondary">
                      {reportPageText.costLoading}
                    </div>
                  ) : (
                    <CostAnalysisChart data={costData} />
                  )}
                  <PeriodCostBreakdown />
                  <SavingsPotentialCard />
                </div>
              )}
              {activeTab === "roi" && <ROICalculator />}
              {activeTab === "vehicle" && (
                <div className="space-y-4">
                  <div>
                    <h2 className="text-base font-semibold text-primary">
                      Araç Tüketim Karşılaştırması
                    </h2>
                    <p className="text-sm text-secondary">
                      Son 3 ay ortalaması, L/100km
                    </p>
                  </div>
                  {vehicleLoading ? (
                    <div className="h-64 animate-pulse rounded-card bg-elevated/50" />
                  ) : vehicleComparison.length === 0 ? (
                    <p className="py-12 text-center text-sm text-secondary">
                      Karşılaştırma verisi yok
                    </p>
                  ) : (
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={vehicleComparison}>
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke="var(--border)"
                          opacity={0.6}
                        />
                        <XAxis
                          dataKey="plaka"
                          tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
                          unit=" L"
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          formatter={(v: number | undefined) => [
                            v != null ? `${v.toFixed(1)} L/100km` : "",
                            "Ort. Tüketim",
                          ]}
                          contentStyle={{
                            backgroundColor: "var(--bg-surface)",
                            border: "1px solid var(--border)",
                            borderRadius: "8px",
                          }}
                          itemStyle={{ color: "var(--text-primary)" }}
                          labelStyle={{ color: "var(--text-secondary)" }}
                        />
                        <Bar
                          dataKey="average_consumption"
                          name="Tüketim"
                          fill="var(--accent)"
                          radius={[4, 4, 0, 0]}
                          cursor="pointer"
                          onClick={(entry) => {
                            const item = (entry as any)?.payload as
                              | { arac_id?: number; plaka?: string }
                              | undefined;
                            if (item?.arac_id && item.plaka) {
                              setDrillDown({
                                aracId: item.arac_id,
                                plaka: item.plaka,
                              });
                            }
                          }}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </ErrorBoundary>
      </div>

      <ExportDialog
        isOpen={isExportDialogOpen}
        onClose={() => setIsExportDialogOpen(false)}
        type={exportType}
        title={exportTitle}
        description={exportDescription}
        onExport={handleExportConfirm}
      />

      {drillDown && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-4xl overflow-hidden rounded-modal border border-border bg-surface shadow-2xl">
            <div className="flex items-center justify-between border-b border-border bg-elevated/40 p-4">
              <h3 className="text-sm font-semibold text-primary">
                Araç Detayı —{" "}
                <span className="font-mono">{drillDown.plaka}</span>
              </h3>
              <button
                onClick={() => setDrillDown(null)}
                className="rounded-full p-1.5 text-secondary transition-colors hover:bg-elevated hover:text-primary"
                aria-label="Kapat"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="p-6">
              <PeriodCostBreakdown
                aracId={drillDown.aracId}
                plakaLabel={drillDown.plaka}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
