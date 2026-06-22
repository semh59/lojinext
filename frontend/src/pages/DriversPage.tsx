import ErrorBoundary from "../components/common/ErrorBoundary";
import { DriversModule } from "../components/modules/DriversModule";
import { usePageTitle } from "../hooks/usePageTitle";
import { useTranslation } from "react-i18next";

export default function DriversPage() {
  const { t } = useTranslation();
  usePageTitle(t("drivers.title", "Drivers"));

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold text-primary">Şoförler</h1>
        <p className="text-sm text-secondary">
          Filo şoförlerini yönetin, performans takibi yapın ve bot
          entegrasyonunu ayarlayın.
        </p>
      </div>

      <ErrorBoundary>
        <DriversModule />
      </ErrorBoundary>
    </div>
  );
}
