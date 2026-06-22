import ErrorBoundary from "../components/common/ErrorBoundary";
import { TripsModule } from "../features/trips/TripsModule";
import { usePageTitle } from "../hooks/usePageTitle";
import { useTripsResources } from "../resources/useResources";

export default function TripsPage() {
  const { tripPageText } = useTripsResources();
  usePageTitle("Seferler");
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold text-primary">
          {tripPageText.heading}
        </h1>
        <p className="text-sm text-secondary">{tripPageText.description}</p>
      </div>

      <ErrorBoundary>
        <div className="glass rounded-modal p-6 shadow-sm">
          <TripsModule />
        </div>
      </ErrorBoundary>
    </div>
  );
}
