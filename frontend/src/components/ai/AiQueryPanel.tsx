import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { aiApi, type AiQueryResponse } from "../../api/ai";
import { useLocale } from "../../hooks/useLocale";

const CATEGORIES = [
  { value: "general", label: "Genel" },
  { value: "fuel_trend", label: "Yakıt Trendi" },
];

type SpeechRecognitionCtor = new () => {
  lang: string;
  onresult: (e: { results: { 0: { 0: { transcript: string } } } }) => void;
  start: () => void;
};

/**
 * Faz 9 — kategori-farkında AI sorgu paneli: kategori seç → sorgu → cevap +
 * otomatik grafik + aksiyon linkleri + Web Speech sesli komut.
 */
export function AiQueryPanel() {
  const [category, setCategory] = useState("general");
  const locale = useLocale();
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<AiQueryResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    if (!message.trim()) return;
    setLoading(true);
    try {
      setResult(await aiApi.query(message, category));
    } finally {
      setLoading(false);
    }
  };

  const startVoice = () => {
    const w = window as unknown as {
      SpeechRecognition?: SpeechRecognitionCtor;
      webkitSpeechRecognition?: SpeechRecognitionCtor;
    };
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!Ctor) return;
    const rec = new Ctor();
    rec.lang = locale;
    rec.onresult = (e) => setMessage(e.results[0][0].transcript);
    rec.start();
  };

  return (
    <div className="rounded-modal border border-border bg-surface p-4 space-y-3">
      <div className="flex gap-2">
        <select
          aria-label="Sorgu kategorisi"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="rounded-card border border-border bg-elevated px-2 py-1 text-sm"
        >
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
        <input
          placeholder="Filo hakkında sor…"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          className="flex-1 rounded-card border border-border bg-elevated px-2 py-1 text-sm"
        />
        <button
          type="button"
          onClick={startVoice}
          aria-label="Sesli komut"
          className="rounded-card bg-elevated px-2 py-1 text-sm"
        >
          🎤
        </button>
        <button
          type="button"
          onClick={run}
          className="rounded-card bg-elevated px-3 py-1 text-sm text-primary"
        >
          {loading ? "…" : "Sorgula"}
        </button>
      </div>

      {result && (
        <div className="space-y-3">
          <p className="whitespace-pre-line text-sm text-primary">
            {result.answer}
          </p>
          {result.chart && (
            <div className="rounded-card border border-border bg-elevated p-3">
              <h4 className="mb-2 text-xs font-semibold text-secondary">
                {result.chart.title}
              </h4>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={result.chart.data}>
                  <XAxis dataKey={result.chart.x_key} fontSize={11} />
                  <YAxis fontSize={11} />
                  <Tooltip />
                  {result.chart.series.map((s) => (
                    <Line
                      key={s.key}
                      type="monotone"
                      dataKey={s.key}
                      name={s.label}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
          {result.actions.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {result.actions.map((a) => (
                <Link
                  key={a.url}
                  to={a.url}
                  className="rounded-card bg-elevated px-3 py-1 text-sm text-accent"
                >
                  {a.label} →
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default AiQueryPanel;
