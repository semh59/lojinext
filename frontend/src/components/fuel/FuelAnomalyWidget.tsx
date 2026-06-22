import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AlertTriangle, ChevronRight, CheckCircle2 } from "lucide-react";
import { Card } from "../ui/Card";
import { Badge } from "../ui/Badge";
import { anomalyService, type RecentAnomaly } from "../../api/anomalies";

const SEVERITY_VARIANT: Record<
  RecentAnomaly["severity"],
  "success" | "info" | "warning" | "danger"
> = {
  low: "info",
  medium: "warning",
  high: "danger",
  critical: "danger",
};

const SEVERITY_LABEL: Record<RecentAnomaly["severity"], string> = {
  low: "Düşük",
  medium: "Orta",
  high: "Yüksek",
  critical: "Kritik",
};

function formatDate(iso: string): string {
  // Backend "YYYY-MM-DD" veya "YYYY-MM-DDTHH:mm:ss" formatında dönüyor.
  // new Date(iso) "YYYY-MM-DD"yi UTC midnight olarak parse eder; TR+3'te bir önceki
  // günü gösterebilir. Önce yyyy-mm-dd kısmını ayıklayıp manuel parçala — saat
  // kaymasından bağımsız "doğru gün/ay" elde edilir.
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) return iso;
  const [, , month, day] = match;
  const monthNames = [
    "Oca",
    "Şub",
    "Mar",
    "Nis",
    "May",
    "Haz",
    "Tem",
    "Ağu",
    "Eyl",
    "Eki",
    "Kas",
    "Ara",
  ];
  return `${day} ${monthNames[Number(month) - 1] ?? month}`;
}

export function FuelAnomalyWidget() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["fuelAnomalyWidget", "tuketim", 30],
    queryFn: () =>
      anomalyService.getRecentAnomalies({ tip: "tuketim", days: 30, limit: 5 }),
    staleTime: 5 * 60 * 1000,
  });

  const items = data?.anomalies ?? [];
  const total = data?.total ?? 0;

  return (
    <Card padding="lg" className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-warning" />
          <h2 className="text-sm font-semibold text-primary">
            Son Yakıt Anomalileri
          </h2>
          {total > 0 && (
            <span className="text-xs font-semibold text-secondary">
              ({total})
            </span>
          )}
        </div>
        {total > items.length && (
          <Link
            to="/alerts?days=30&tip=tuketim"
            className="inline-flex items-center gap-0.5 text-xs font-medium text-accent hover:underline"
          >
            Tüm Anomaliler <ChevronRight className="h-3 w-3" />
          </Link>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-12 animate-pulse rounded-card bg-elevated/50"
            />
          ))}
        </div>
      ) : isError ? (
        <p className="text-sm text-secondary">Anomaliler yüklenemedi</p>
      ) : items.length === 0 ? (
        <div className="flex items-center gap-2 rounded-card border border-success/20 bg-success/5 px-4 py-3">
          <CheckCircle2 className="h-4 w-4 text-success" />
          <p className="text-sm text-secondary">
            Son 30 günde yakıt anomalisi tespit edilmedi
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {items.map((a) => (
            <li
              key={a.id}
              className="flex items-center justify-between gap-3 rounded-card border border-border/50 bg-elevated/30 px-3 py-2"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-primary">
                  {a.plaka ?? `Araç #${a.kaynak_id}`}
                  {a.sofor_adi ? (
                    <span className="ml-2 text-xs text-secondary">
                      · {a.sofor_adi}
                    </span>
                  ) : null}
                </p>
                <p className="text-[11px] text-secondary">
                  {formatDate(a.tarih)} · sapma %{a.sapma_yuzde.toFixed(1)}
                </p>
              </div>
              <Badge variant={SEVERITY_VARIANT[a.severity]}>
                {SEVERITY_LABEL[a.severity]}
              </Badge>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
