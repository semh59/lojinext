import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { chartTheme } from "../lib/chart-theme";
import { FuelTable } from "../components/fuel/FuelTable";
import { FuelModal } from "../components/fuel/FuelModal";
import { ReceiptUpload } from "../components/fuel/ReceiptUpload";
import { FuelStats } from "../components/fuel/FuelStats";
import { FuelHeader } from "../components/fuel/FuelHeader";
import { FuelFilters } from "../components/fuel/FuelFilters";
import { ComparisonWidget } from "../components/fuel/ComparisonWidget";
import { FuelAnomalyWidget } from "../components/fuel/FuelAnomalyWidget";
import { CostTrendChart } from "../components/fuel/CostTrendChart";
import { FuelPagination } from "../components/fuel/FuelPagination";
import { FuelRecord } from "../types";
import ErrorBoundary from "../components/common/ErrorBoundary";
import { useNotify } from "../context/NotificationContext";
import { useUrlState } from "../hooks/use-url-state";
import { usePageTitle } from "../hooks/usePageTitle";
import { fuelService, type OcrPreview } from "../api/fuel";
import { predictionService } from "../api/predictions";
import { vehicleService } from "../api/vehicles";
import { reportService } from "../api/reports";
import { Card } from "../components/ui/Card";
import { useFuelResources } from "../resources/useResources";
import { useLocale } from "../hooks/useLocale";
import { useTranslation } from "react-i18next";

export default function FuelPage() {
  const { fuelPageText } = useFuelResources();
  const { t } = useTranslation();
  const locale = useLocale();
  usePageTitle(t("fuel.title", "Fuel"));
  const { notify } = useNotify();
  const queryClient = useQueryClient();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState<FuelRecord | null>(null);
  // Faz 6 — OCR önizlemesinden gelen yeni-kayıt ön-doldurma değerleri.
  const [ocrPrefill, setOcrPrefill] = useState<Record<string, unknown> | null>(
    null,
  );

  const handleOcrConfirm = (f: OcrPreview["yapilandirilmis"]) => {
    // OCR "GG/AA/YYYY" veya "GG.AA.YYYY" → ISO "YYYY-AA-GG"
    let isoTarih: string | undefined;
    const m = f.tarih?.match(/^(\d{2})[./](\d{2})[./](\d{4})$/);
    if (m) isoTarih = `${m[3]}-${m[2]}-${m[1]}`;
    const litre = f.litre ?? undefined;
    const tutar = f.tutar ?? undefined;
    const prefill: Record<string, unknown> = {};
    if (isoTarih) prefill.tarih = isoTarih;
    if (litre != null) prefill.litre = litre;
    if (f.km != null) prefill.km_sayac = f.km;
    if (f.istasyon) prefill.istasyon = f.istasyon;
    // OCR toplam tutar verir; birim fiyatı litreden türet (varsa).
    if (litre && tutar) prefill.fiyat_tl = Number((tutar / litre).toFixed(2));
    setSelectedRecord(null);
    setOcrPrefill(prefill);
    setIsModalOpen(true);
  };

  const [filters, setFilters] = useUrlState({
    page: 1,
    start: new Date(new Date().setMonth(new Date().getMonth() - 1))
      .toISOString()
      .slice(0, 10),
    end: new Date().toISOString().slice(0, 10),
    vehicle: "",
  });

  const {
    page,
    start: startDate,
    end: endDate,
    vehicle: vehicleFilter,
  } = filters;
  const pageSize = 20;

  const { data: vehiclesData = [] } = useQuery({
    queryKey: ["vehicles", "minimal"],
    queryFn: () => vehicleService.getAll({ limit: 100 }),
    staleTime: 30 * 60 * 1000,
  });
  const vehicles: any[] = Array.isArray(vehiclesData)
    ? vehiclesData
    : (vehiclesData as any)?.items || [];

  const [comparisonVehicleId, setComparisonVehicleId] = useState<number | null>(
    null,
  );

  const { data: comparisonData, isLoading: isComparisonLoading } = useQuery({
    queryKey: ["predictionComparison", comparisonVehicleId],
    queryFn: () =>
      predictionService.getComparison(30, comparisonVehicleId ?? undefined),
    staleTime: 15 * 60 * 1000,
  });

  const { data: recordsResult, isLoading: isRecordsLoading } = useQuery({
    queryKey: [
      "fuelRecords",
      { startDate, endDate, vehicleFilter, page, pageSize },
    ],
    queryFn: () =>
      fuelService.getAll({
        baslangic_tarih: startDate,
        bitis_tarih: endDate,
        arac_id: vehicleFilter ? Number(vehicleFilter) : undefined,
        skip: (page - 1) * pageSize,
        limit: pageSize,
      }),
    staleTime: 5 * 60 * 1000,
  });
  const records = recordsResult?.items || [];
  const totalRecords = recordsResult?.total || 0;

  const { data: stats, isLoading: isStatsLoading } = useQuery({
    queryKey: ["fuelStats", { startDate, endDate, vehicleFilter }],
    queryFn: () =>
      fuelService.getStats({
        baslangic_tarih: startDate,
        bitis_tarih: endDate,
        arac_id: vehicleFilter ? Number(vehicleFilter) : undefined,
      }),
    staleTime: 5 * 60 * 1000,
  });

  const { data: trend = [], isLoading: trendLoading } = useQuery({
    queryKey: ["fuel-consumption-trend"],
    queryFn: () => reportService.getConsumptionTrend(),
    staleTime: 10 * 60 * 1000,
  });

  const handleSave = async (data: Partial<FuelRecord>) => {
    try {
      const payload = {
        ...data,
        fiyat_tl: data.birim_fiyat || (data as any).fiyat_tl,
      };
      if (selectedRecord?.id) {
        await fuelService.update(selectedRecord.id, payload);
        notify(
          "success",
          fuelPageText.notifications.updateSuccessTitle,
          fuelPageText.notifications.updateSuccessMessage,
        );
      } else {
        await fuelService.create(payload);
        notify(
          "success",
          fuelPageText.notifications.createSuccessTitle,
          fuelPageText.notifications.createSuccessMessage,
        );
        setFilters({ page: 1 });
      }

      if (data.tarih) {
        if (data.tarih > endDate) setFilters({ end: data.tarih });
        if (data.tarih < startDate) setFilters({ start: data.tarih });
      }

      queryClient.invalidateQueries({ queryKey: ["fuelRecords"] });
      queryClient.invalidateQueries({ queryKey: ["fuelStats"] });
      setIsModalOpen(false);
    } catch {
      notify(
        "error",
        fuelPageText.notifications.actionErrorTitle,
        fuelPageText.notifications.actionErrorMessage,
      );
    }
  };

  const handleDelete = async (record: FuelRecord) => {
    if (!window.confirm(fuelPageText.notifications.deleteConfirm)) return;

    try {
      await fuelService.delete(record.id!);
      notify(
        "success",
        fuelPageText.notifications.deleteSuccessTitle,
        fuelPageText.notifications.deleteSuccessMessage,
      );
      queryClient.invalidateQueries({ queryKey: ["fuelRecords"] });
      queryClient.invalidateQueries({ queryKey: ["fuelStats"] });
    } catch (error: any) {
      notify(
        "error",
        fuelPageText.notifications.actionErrorTitle,
        error.response?.data?.detail ||
          fuelPageText.notifications.deleteErrorFallback,
      );
    }
  };

  const handleExport = async () => {
    try {
      const blob = await fuelService.exportExcel({
        baslangic_tarih: startDate,
        bitis_tarih: endDate,
        arac_id: vehicleFilter ? Number.parseInt(vehicleFilter, 10) : undefined,
      });
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${fuelPageText.exportFileNamePrefix}_${
        new Date().toISOString().split("T")[0]
      }.xlsx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      notify(
        "success",
        fuelPageText.notifications.exportSuccessTitle,
        fuelPageText.notifications.exportSuccessMessage,
      );
    } catch {
      notify(
        "error",
        fuelPageText.notifications.actionErrorTitle,
        fuelPageText.notifications.exportErrorMessage,
      );
    }
  };

  const handleDownloadTemplate = async () => {
    try {
      const blob = await fuelService.downloadTemplate();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = fuelPageText.templateFileName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      notify(
        "error",
        fuelPageText.notifications.actionErrorTitle,
        fuelPageText.notifications.templateErrorMessage,
      );
    }
  };

  const handleImport = async (file: File) => {
    try {
      await fuelService.uploadExcel(file);
      notify(
        "success",
        fuelPageText.notifications.importSuccessTitle,
        fuelPageText.notifications.importSuccessMessage,
      );
      queryClient.invalidateQueries({ queryKey: ["fuelRecords"] });
      queryClient.invalidateQueries({ queryKey: ["fuelStats"] });
    } catch {
      notify(
        "error",
        fuelPageText.notifications.actionErrorTitle,
        fuelPageText.notifications.importErrorMessage,
      );
    }
  };

  return (
    <div className="space-y-6">
      {/* Başlık + aksiyonlar */}
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold text-primary">
            {fuelPageText.heading}
          </h1>
          <p className="text-sm text-secondary">{fuelPageText.description}</p>
        </div>
        <FuelHeader
          onAdd={() => {
            setSelectedRecord(null);
            setOcrPrefill(null);
            setIsModalOpen(true);
          }}
          onExport={handleExport}
          onDownloadTemplate={handleDownloadTemplate}
          onImport={handleImport}
        />
      </div>

      {/* Faz 6 — fiş fotoğrafı yükle → OCR önizleme → onayla → kayıt formu */}
      <ReceiptUpload onConfirm={handleOcrConfirm} />

      <div className="grid grid-cols-1 gap-6">
        <FuelStats stats={stats ?? null} loading={isStatsLoading} />

        {comparisonData ? (
          <ComparisonWidget
            data={comparisonData}
            isLoading={isComparisonLoading}
            vehicles={vehicles.map((v: any) => ({ id: v.id, plaka: v.plaka }))}
            selectedVehicleId={comparisonVehicleId}
            onVehicleChange={setComparisonVehicleId}
          />
        ) : null}

        {/* Tüketim + Maliyet trend grafikleri (2-sütun) */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card padding="lg">
            <div className="mb-4">
              <h2 className="text-sm font-semibold text-primary">
                {t("fuel.monthly_trend_title")}
              </h2>
              <p className="text-xs text-secondary">
                {t("fuel.monthly_trend_subtitle")}
              </p>
            </div>
            {trendLoading ? (
              <div className="h-36 animate-pulse rounded-card bg-elevated/50" />
            ) : (
              <ResponsiveContainer width="100%" height={144}>
                <LineChart data={trend}>
                  <CartesianGrid {...chartTheme.grid} />
                  <XAxis
                    dataKey="month"
                    tick={chartTheme.tickSmall}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={chartTheme.tick}
                    unit=" L"
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    {...chartTheme.tooltip}
                    formatter={(v: number | undefined) => [
                      v != null
                        ? `${v.toLocaleString(locale, {
                            maximumFractionDigits: 1,
                          })} L`
                        : "",
                      t("fuel.consumption_tooltip"),
                    ]}
                  />
                  <Line
                    type="monotone"
                    dataKey="consumption"
                    stroke={chartTheme.colors.accent}
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Card>

          <CostTrendChart />
        </div>

        <FuelAnomalyWidget />

        <div className="glass rounded-modal border border-border p-6 shadow-sm">
          <FuelFilters
            startDate={startDate}
            setStartDate={(value) => setFilters({ start: value })}
            endDate={endDate}
            setEndDate={(value) => setFilters({ end: value })}
            vehicleFilter={vehicleFilter}
            setVehicleFilter={(value) => setFilters({ vehicle: value })}
            vehicles={vehicles}
            onFilter={() => {
              setFilters({ page: 1 });
              queryClient.invalidateQueries({ queryKey: ["fuelRecords"] });
              queryClient.invalidateQueries({ queryKey: ["fuelStats"] });
            }}
            onReset={() =>
              setFilters({
                page: 1,
                start: new Date(new Date().setMonth(new Date().getMonth() - 1))
                  .toISOString()
                  .slice(0, 10),
                end: new Date().toISOString().slice(0, 10),
                vehicle: "",
              })
            }
          />

          <div className="mt-8 overflow-hidden border-t border-border pt-6">
            <ErrorBoundary>
              <FuelTable
                records={records}
                loading={isRecordsLoading}
                onEdit={(record) => {
                  setSelectedRecord(record);
                  setIsModalOpen(true);
                }}
                onDelete={handleDelete}
              />

              <div className="mt-4">
                <FuelPagination
                  currentPage={page}
                  totalCount={totalRecords}
                  pageSize={pageSize}
                  onPageChange={(nextPage) => setFilters({ page: nextPage })}
                />
              </div>
            </ErrorBoundary>
          </div>
        </div>
      </div>

      <FuelModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        record={selectedRecord}
        ocrPrefill={ocrPrefill}
        onSave={handleSave}
      />
    </div>
  );
}
