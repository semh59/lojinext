import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  BrainCircuit,
  Loader2,
  RefreshCw,
  Send,
  Sparkles,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { Card } from "../ui/Card";
import { cn } from "../../lib/utils";
import {
  coachingService,
  type CoachingCategory,
  type CoachingInsight,
  type CoachingPriority,
} from "../../api/coaching";
import { useCoachingResources } from "../../resources/useResources";
import { useLocale } from "../../hooks/useLocale";
import { useTranslation } from "react-i18next";

interface CoachingInsightsPanelProps {
  soforId: number | null;
  onSendClick?: (insight: CoachingInsight) => void;
}

const CATEGORY_STYLE: Record<CoachingCategory, { bg: string; text: string }> = {
  yakit_yonetimi: { bg: "bg-info/10", text: "text-info" },
  guzergah_tercihi: { bg: "bg-accent/10", text: "text-accent" },
  sofor_pratigi: { bg: "bg-warning/10", text: "text-warning" },
  diger: { bg: "bg-elevated", text: "text-secondary" },
};

const PRIORITY_STYLE: Record<
  CoachingPriority,
  { bg: string; text: string; border: string }
> = {
  low: { bg: "bg-elevated", text: "text-secondary", border: "border-border" },
  medium: {
    bg: "bg-warning/10",
    text: "text-warning",
    border: "border-warning/30",
  },
  high: { bg: "bg-danger/10", text: "text-danger", border: "border-danger/30" },
};

export function CoachingInsightsPanel({
  soforId,
  onSendClick,
}: CoachingInsightsPanelProps) {
  const { t } = useTranslation();
  const { coachingCategoryLabels, coachingPageText, coachingPriorityLabels } =
    useCoachingResources();
  const locale = useLocale();
  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["coaching", "insights", soforId],
    queryFn: () => coachingService.getInsights(soforId!),
    enabled: soforId !== null,
    staleTime: 30 * 60 * 1000, // Backend ile aynı cache penceresi
  });

  if (soforId === null) {
    return (
      <Card
        padding="lg"
        className="flex h-full min-h-[400px] items-center justify-center"
      >
        <div className="flex flex-col items-center gap-2 text-center">
          <BrainCircuit className="h-8 w-8 text-tertiary" />
          <p className="text-sm text-secondary">
            {coachingPageText.selectDriverHint}
          </p>
        </div>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card
        padding="lg"
        className="flex h-full min-h-[400px] items-center justify-center"
      >
        <div className="flex items-center gap-2 text-secondary text-sm">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t("coaching.insights_loading")}
        </div>
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card padding="lg" className="flex h-full items-start gap-2">
        <AlertCircle className="h-5 w-5 text-danger" />
        <p className="text-sm text-danger">{coachingPageText.errorLoad}</p>
      </Card>
    );
  }

  const priority = PRIORITY_STYLE[data.priority];

  return (
    <Card padding="lg" className="space-y-5">
      {/* Headline */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-base font-bold text-primary truncate">
              {data.ad_soyad}
            </h2>
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider",
                priority.border,
                priority.bg,
                priority.text,
              )}
            >
              {t("coaching.priority_badge", {
                label: coachingPriorityLabels[data.priority],
              })}
            </span>
          </div>
          {data.insights.length > 0 && (
            <p className="text-sm text-secondary leading-relaxed">
              {data.headline}
            </p>
          )}
          <p className="mt-1 text-[10px] font-mono text-tertiary">
            {data.source === "llm"
              ? coachingPageText.sourceLlm
              : coachingPageText.sourceFallback}
            {" · "}
            {new Date(data.generated_at).toLocaleString(locale, {
              day: "2-digit",
              month: "short",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            queryClient.invalidateQueries({
              queryKey: ["coaching", "insights", soforId],
            });
          }}
          title={coachingPageText.refresh}
          aria-label={coachingPageText.refresh}
          className="rounded-card border border-border p-2 text-secondary transition-colors hover:bg-elevated hover:text-primary"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>

      {data.insights.length === 0 ? (
        <div className="flex items-center gap-2 rounded-card border border-success/20 bg-success/5 px-4 py-3">
          <Sparkles className="h-4 w-4 text-success" />
          <p className="text-sm text-secondary">
            {coachingPageText.emptyInsights}
          </p>
        </div>
      ) : (
        <ul className="space-y-3">
          {data.insights.map((insight, idx) => {
            const cat = CATEGORY_STYLE[insight.category];
            return (
              <li
                key={idx}
                className="rounded-modal border border-border bg-elevated/30 p-4 space-y-2"
              >
                <div className="flex items-baseline justify-between gap-3 flex-wrap">
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider",
                      cat.bg,
                      cat.text,
                    )}
                  >
                    {coachingCategoryLabels[insight.category] ??
                      insight.category}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] font-bold uppercase tracking-widest text-secondary">
                      {t("coaching.impact_label")}
                    </span>
                    <div className="h-1.5 w-16 overflow-hidden rounded-full bg-elevated">
                      <div
                        className="h-full bg-accent"
                        style={{ width: `${insight.impact_score * 100}%` }}
                      />
                    </div>
                    <span className="font-mono text-[10px] text-secondary tabular-nums">
                      {Math.round(insight.impact_score * 100)}%
                    </span>
                  </div>
                </div>
                <p className="text-sm font-semibold text-primary">
                  {insight.pattern}
                </p>
                {insight.evidence.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {insight.evidence.map((ev, eIdx) => (
                      <span
                        key={eIdx}
                        className="rounded-card bg-elevated px-2 py-0.5 text-[10px] font-mono text-secondary"
                      >
                        {ev}
                      </span>
                    ))}
                  </div>
                )}
                <p className="text-sm text-secondary leading-relaxed">
                  💡 {insight.suggestion}
                </p>
                {onSendClick && (
                  <div className="flex justify-end pt-1">
                    <button
                      type="button"
                      onClick={() => onSendClick(insight)}
                      className="inline-flex items-center gap-1.5 rounded-card border border-accent/30 bg-accent/5 px-3 py-1.5 text-xs font-semibold text-accent transition-colors hover:bg-accent/10"
                    >
                      <Send className="h-3 w-3" />
                      {t("coaching.send_telegram")}
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
