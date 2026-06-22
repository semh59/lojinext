import { useState } from "react";
import type { Driver } from "../types";
import { CoachingDriverList } from "../components/coaching/CoachingDriverList";
import { CoachingInsightsPanel } from "../components/coaching/CoachingInsightsPanel";
import { EffectivenessMiniCard } from "../components/coaching/EffectivenessMiniCard";
import { SendCoachingDialog } from "../components/coaching/SendCoachingDialog";
import { usePageTitle } from "../hooks/usePageTitle";
import type { CoachingInsight } from "../api/coaching";
import { useCoachingResources } from "../resources/useResources";
import { useTranslation } from "react-i18next";

export default function CoachingPage() {
  const { coachingPageText } = useCoachingResources();
  const { t } = useTranslation();
  usePageTitle(t("nav.coaching", "Coaching"));
  const [selectedDriver, setSelectedDriver] = useState<Driver | null>(null);
  const [activeInsight, setActiveInsight] = useState<CoachingInsight | null>(
    null,
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-primary">
          {coachingPageText.heading}
        </h1>
        <p className="text-sm text-secondary">{coachingPageText.description}</p>
      </div>

      <EffectivenessMiniCard days={30} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
        <CoachingDriverList
          selectedDriverId={selectedDriver?.id ?? null}
          onSelect={setSelectedDriver}
        />
        <CoachingInsightsPanel
          soforId={selectedDriver?.id ?? null}
          onSendClick={setActiveInsight}
        />
      </div>

      <SendCoachingDialog
        soforId={selectedDriver?.id ?? null}
        soforAdi={selectedDriver?.ad_soyad ?? ""}
        insight={activeInsight}
        onClose={() => setActiveInsight(null)}
      />
    </div>
  );
}
