import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Info, Loader2 } from "lucide-react";
import { investigationsText } from "../../resources/tr/investigations";
import { investigationService } from "../../api/investigations";

function formatDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${m[3]}.${m[2]}.${m[1]}`;
}

export function PatternList() {
  const [days, setDays] = useState(30);
  const [minCount, setMinCount] = useState(3);

  const { data = [], isLoading } = useQuery({
    queryKey: ["investigations", "patterns", days, minCount],
    queryFn: () =>
      investigationService.getPatterns({
        days,
        min_count: minCount,
        limit: 50,
      }),
    staleTime: 5 * 60 * 1000,
  });

  return (
    <div className="space-y-3 rounded-modal border border-border bg-surface p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-primary">
            {investigationsText.pattern.title}
          </h3>
          <p className="text-[11px] text-secondary">
            {investigationsText.pattern.subtitle(days)}
          </p>
        </div>
        <div className="flex items-center gap-3 text-[11px]">
          <label className="flex items-center gap-1 text-secondary">
            {investigationsText.pattern.daysLabel}
            <input
              type="number"
              min={7}
              max={180}
              value={days}
              onChange={(e) =>
                setDays(
                  Math.max(7, Math.min(180, Number(e.target.value) || 30)),
                )
              }
              className="h-7 w-16 rounded-card border border-border bg-elevated px-2 text-xs"
            />
          </label>
          <label className="flex items-center gap-1 text-secondary">
            {investigationsText.pattern.minCountLabel}
            <input
              type="number"
              min={1}
              max={10}
              value={minCount}
              onChange={(e) =>
                setMinCount(
                  Math.max(1, Math.min(10, Number(e.target.value) || 3)),
                )
              }
              className="h-7 w-14 rounded-card border border-border bg-elevated px-2 text-xs"
            />
          </label>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 py-3 text-secondary text-xs">
          <Loader2 className="h-3 w-3 animate-spin" />
        </div>
      ) : data.length === 0 ? (
        <div className="flex items-center gap-2 rounded-card border border-success/20 bg-success/5 px-3 py-2 text-xs text-secondary">
          <Info className="h-3.5 w-3.5 text-success" />
          {investigationsText.pattern.empty}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-elevated/40">
              <tr>
                <th className="px-3 py-2 text-left font-bold uppercase tracking-wider text-secondary">
                  {investigationsText.pattern.columns.sofor}
                </th>
                <th className="px-3 py-2 text-left font-bold uppercase tracking-wider text-secondary">
                  {investigationsText.pattern.columns.plaka}
                </th>
                <th className="px-3 py-2 text-right font-bold uppercase tracking-wider text-secondary">
                  {investigationsText.pattern.columns.count}
                </th>
                <th className="px-3 py-2 text-right font-bold uppercase tracking-wider text-secondary">
                  {investigationsText.pattern.columns.avgScore}
                </th>
                <th className="px-3 py-2 text-right font-bold uppercase tracking-wider text-secondary">
                  {investigationsText.pattern.columns.lastSeen}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {data.map((p, idx) => (
                <tr key={idx} className="hover:bg-elevated/30">
                  <td className="px-3 py-2 text-primary">
                    {p.sofor_adi ?? "—"}
                  </td>
                  <td className="px-3 py-2 font-mono text-primary">
                    {p.plaka ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right font-mono tabular-nums">
                    {p.occurrence_count}
                  </td>
                  <td className="px-3 py-2 text-right font-mono tabular-nums font-semibold text-warning">
                    {p.avg_suspicion_score.toFixed(2)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-tertiary">
                    {formatDate(p.last_seen)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
