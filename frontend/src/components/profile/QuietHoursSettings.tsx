import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { preferenceService } from "../../api/preferences";

interface QuietHours {
  enabled: boolean;
  start: string;
  end: string;
}

const DEFAULT: QuietHours = { enabled: false, start: "22:00", end: "07:00" };

export function QuietHoursSettings() {
  const { t } = useTranslation();
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
      <h3 className="text-sm font-semibold text-secondary">
        {t("profile.quiet_hours_title", "Quiet Hours")}
      </h3>
      <label className="flex items-center gap-2 text-sm text-primary">
        <input
          type="checkbox"
          checked={qh.enabled}
          onChange={(e) => setQh({ ...qh, enabled: e.target.checked })}
        />
        {t(
          "profile.quiet_hours_no_notify",
          "Do not send notifications during quiet hours",
        )}
      </label>
      <div className="flex items-center gap-3">
        <label className="text-sm text-tertiary">
          {t("profile.quiet_hours_start", "Start")}
          <input
            type="time"
            aria-label={t(
              "profile.quiet_hours_start_aria",
              "Quiet hours start",
            )}
            value={qh.start}
            onChange={(e) => setQh({ ...qh, start: e.target.value })}
            className="ml-2 rounded-card border border-border bg-elevated px-2 py-1"
          />
        </label>
        <label className="text-sm text-tertiary">
          {t("profile.quiet_hours_end", "End")}
          <input
            type="time"
            aria-label={t("profile.quiet_hours_end_aria", "Quiet hours end")}
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
        {saved
          ? t("profile.quiet_hours_saved", "Saved ✓")
          : t("profile.quiet_hours_save", "Save quiet hours")}
      </button>
    </div>
  );
}

export default QuietHoursSettings;
