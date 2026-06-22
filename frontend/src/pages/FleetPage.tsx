import { AnimatePresence, motion } from "framer-motion";
import { Container, Truck } from "lucide-react";

import ErrorBoundary from "../components/common/ErrorBoundary";
import { FleetInsights } from "../components/fleet/FleetInsights";
import { TrailersModule } from "../components/modules/TrailersModule";
import { VehiclesModule } from "../components/modules/VehiclesModule";
import { usePageTitle } from "../hooks/usePageTitle";
import { useUrlState } from "../hooks/use-url-state";
import { cn } from "../lib/utils";
import { fleetPageText } from "../resources/tr/fleet";

type TabType = "vehicles" | "trailers";

export default function FleetPage() {
  usePageTitle("Araçlar & Dorseler");
  const [{ tab: activeTab }, setUrlState] = useUrlState({
    tab: "vehicles" as TabType,
    page: undefined as number | undefined,
    search: undefined as string | undefined,
    marka: undefined as string | undefined,
    model: undefined as string | undefined,
    min_yil: undefined as string | undefined,
    max_yil: undefined as string | undefined,
    aktif: undefined as boolean | undefined,
    view: undefined as string | undefined,
  });

  const handleTabChange = (tab: TabType) => {
    setUrlState({
      tab,
      page: undefined,
      search: undefined,
      marka: undefined,
      model: undefined,
      min_yil: undefined,
      max_yil: undefined,
      aktif: undefined,
      view: undefined,
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold text-primary">Araçlar & Dorseler</h1>
        <p className="text-sm text-secondary">{fleetPageText.description}</p>
      </div>

      <FleetInsights activeTab={activeTab} />

      <div className="flex p-1.5 bg-surface border border-border rounded-modal w-fit shadow-sm relative glass">
        <button
          onClick={() => handleTabChange("vehicles")}
          className={cn(
            "relative flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 z-10",
            activeTab === "vehicles"
              ? "text-white"
              : "text-tertiary hover:text-secondary",
          )}
        >
          {activeTab === "vehicles" && (
            <motion.div
              layoutId="fleetTabIndicator"
              className="absolute inset-0 bg-accent rounded-xl -z-10 shadow-md shadow-accent/20"
              transition={{ type: "spring", bounce: 0.15, duration: 0.4 }}
            />
          )}
          <Truck size={18} />
          {fleetPageText.tabs.vehicles}
        </button>

        <button
          onClick={() => handleTabChange("trailers")}
          className={cn(
            "relative flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 z-10",
            activeTab === "trailers"
              ? "text-white"
              : "text-tertiary hover:text-secondary",
          )}
        >
          {activeTab === "trailers" && (
            <motion.div
              layoutId="fleetTabIndicator"
              className="absolute inset-0 bg-accent rounded-xl -z-10 shadow-md shadow-accent/20"
              transition={{ type: "spring", bounce: 0.15, duration: 0.4 }}
            />
          )}
          <Container size={18} />
          {fleetPageText.tabs.trailers}
        </button>
      </div>

      <ErrorBoundary>
        <div className="glass rounded-modal shadow-sm border border-border overflow-hidden">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, x: 5 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -5 }}
              transition={{ duration: 0.25, ease: "easeOut" }}
              className="p-6"
            >
              {activeTab === "vehicles" ? (
                <VehiclesModule />
              ) : (
                <TrailersModule />
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </ErrorBoundary>
    </div>
  );
}
