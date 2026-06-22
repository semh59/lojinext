import { useEffect, useState } from "react";
import { preferenceService } from "../../api/preferences";

interface QuietHours {
  enabled: boolean;
  start: string;
  end: string;
}

const DEFAULT: QuietHours = { enabled: false, start: "22:00", end: "07:00" };

/**
 * Faz 5 — sessiz saat ayarı. /preferences (modul='bildirim',
 * ayar_tipi='quiet_hours') üzerinden saklanır.
 */
export function QuietHoursSettings() {
  const [qh, setQh] = useState<QuietHours>(DEFAULT);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let active = true;
    preferenceService
      .getPreferences("bildirim", "quiet_hours")
      .then((res: unknown) => {
        if (!active) return;
        const items =
          (res as { items?: { deger?: Partial<QuietHours> }[] })?.items ??
          (res as { deger?: Partial<QuietHours> }[]);
        const deger = Array.isArray(items) ? items[0]?.deger : undefined;
        if (deger) setQh({ ...DEFAULT, ...deger });
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  const save = async () => {
    await preferenceService.savePreference({
      modul: "bildirim",
      ayar_tipi: "quiet_hours",
      deger: qh,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="rounded-modal border border-border bg-surface p-4 space-y-3">
      <h3 className="text-sm font-semibold text-secondary">Sessiz Saatler</h3>
      <label className="flex items-center gap-2 text-sm text-primary">
        <input
          type="checkbox"
          checked={qh.enabled}
          onChange={(e) => setQh({ ...qh, enabled: e.target.checked })}
        />
        Sessiz saatlerde bildirim gönderme
      </label>
      <div className="flex items-center gap-3">
        <label className="text-sm text-tertiary">
          Başlangıç
          <input
            type="time"
            aria-label="Sessiz saat başlangıç"
            value={qh.start}
            onChange={(e) => setQh({ ...qh, start: e.target.value })}
            className="ml-2 rounded-card border border-border bg-elevated px-2 py-1"
          />
        </label>
        <label className="text-sm text-tertiary">
          Bitiş
          <input
            type="time"
            aria-label="Sessiz saat bitiş"
            value={qh.end}
            onChange={(e) => setQh({ ...qh, end: e.target.value })}
            className="ml-2 rounded-card border border-border bg-elevated px-2 py-1"
          />
        </label>
      </div>
      <button
        type="button"
        onClick={save}
        className="rounded-card bg-elevated px-3 py-1 text-sm text-primary"
      >
        {saved ? "Kaydedildi ✓" : "Sessiz saatleri kaydet"}
      </button>
    </div>
  );
}

export default QuietHoursSettings;
