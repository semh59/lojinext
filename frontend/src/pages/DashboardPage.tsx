import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  Truck,
  AlertTriangle,
  Target,
  Route,
  CalendarDays,
} from "lucide-react";
import { KpiRow } from "@/components/dashboard/KpiRow";
import { ConsumptionChart } from "@/components/dashboard/ConsumptionChart";
import { AnomalyWidget } from "@/components/dashboard/AnomalyWidget";
import { TodaysActiveTrips } from "@/components/dashboard/TodaysActiveTrips";
import { reportService } from "@/api/reports";
import { anomalyService } from "@/api/anomalies";
import { predictionService } from "@/api/predictions";
import { tripService } from "@/api/trips";

export default function DashboardPage() {
  const navigate = useNavigate();

  const { data: stats } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: () => reportService.getDashboardStats(),
    staleTime: 60 * 1000,
    refetchOnWindowFocus: true,
  });

  const { data: tripStats } = useQuery({
    queryKey: ["dashboard-trip-stats"],
    queryFn: () => tripService.getStats(),
    staleTime: 60 * 1000,
    refetchOnWindowFocus: true,
  });

  const { data: trend = [], isLoading: trendLoading } = useQuery({
    queryKey: ["dashboard-consumption-trend"],
    queryFn: () => reportService.getConsumptionTrend(),
    staleTime: 10 * 60 * 1000,
  });

  const { data: insights, isLoading: insightsLoading } = useQuery({
    queryKey: ["dashboard-fleet-insights"],
    queryFn: () => anomalyService.getFleetInsights(30),
    staleTime: 5 * 60 * 1000,
  });

  const { data: comparison } = useQuery({
    queryKey: ["dashboard-prediction-comparison"],
    queryFn: () => predictionService.getComparison(30),
    staleTime: 10 * 60 * 1000,
  });

  const totalAlerts =
    (insights?.maintenance.urgent_count ?? 0) +
    (insights?.maintenance.warning_count ?? 0);

  const kpiItems = [
    {
      label: "Toplam Sefer",
      value: tripStats?.total_count ?? "—",
      icon: Activity,
      color: "text-info",
      bgColor: "bg-info/10",
      trend: stats?.trends?.sefer,
    },
    {
      label: "Aktif Araç",
      value: stats?.aktif_arac ?? "—",
      icon: Truck,
      color: "text-accent",
      bgColor: "bg-accent/10",
    },
    {
      label: "Bugün",
      value: stats?.bugun_sefer ?? "—",
      icon: CalendarDays,
      color: "text-info",
      bgColor: "bg-info/10",
      // Günlük metrik için aylık trend yanıltıcı — bilinçli olarak eklenmedi.
    },
    {
      label: "Bakım Adayı",
      value: totalAlerts,
      icon: AlertTriangle,
      color: "text-warning",
      bgColor: "bg-warning/10",
    },
    {
      label: "Yoldaki Sefer",
      value: tripStats?.in_progress_count ?? "—",
      icon: Route,
      color: "text-accent",
      bgColor: "bg-accent/10",
    },
    {
      label: "ML Doğruluk",
      value: comparison
        ? `${comparison.accuracy_distribution.good_pct.toFixed(0)}%`
        : "—",
      icon: Target,
      color: "text-success",
      bgColor: "bg-success/10",
    },
  ];

  return (
    <div data-testid="dashboard-page" className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-primary">Filo Paneli</h1>
        <p className="text-sm text-secondary">Filo genel durumu ve özeti</p>
      </div>

      <KpiRow items={kpiItems} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ConsumptionChart data={trend} isLoading={trendLoading} />
        <button
          type="button"
          onClick={() => navigate("/alerts?days=30")}
          className="text-left rounded-modal focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
          aria-label="Tüm uyarıları görüntüle"
        >
          <AnomalyWidget data={insights} isLoading={insightsLoading} />
        </button>
      </div>

      <TodaysActiveTrips />
    </div>
  );
}
