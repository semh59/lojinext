import { useState } from "react";
import { Crosshair } from "lucide-react";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { AnalysisResponse, Location } from "../../types/location";
import { RouteAnalysisCard } from "./RouteAnalysisCard";
import { CalibrationModal } from "./CalibrationModal";
import { useLocationsResources } from "../../resources/useResources";

interface AnalysisModalProps {
  isOpen: boolean;
  onClose: () => void;
  location: Location | null;
  analysisData: AnalysisResponse | null;
  isLoading: boolean;
  onAnalyze: () => void;
}

export function AnalysisModal({
  isOpen,
  onClose,
  location,
  analysisData,
  isLoading,
  onAnalyze,
}: AnalysisModalProps) {
  const { analysisModalText } = useLocationsResources();
  const [isCalibrationOpen, setIsCalibrationOpen] = useState(false);
  if (!location) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex flex-col">
          <span className="text-primary">{analysisModalText.title}</span>
          <span className="mt-1 text-sm font-normal text-secondary">
            {analysisModalText.routeSummary(
              location.cikis_yeri,
              location.varis_yeri,
              location.mesafe_km,
            )}
          </span>
        </div>
      }
      size="lg"
      className="max-w-4xl"
    >
      <div className="space-y-6">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="mb-4 h-16 w-16 animate-spin rounded-full border-4 border-accent/20 border-t-accent" />
            <p className="font-medium text-secondary">
              {analysisModalText.loading}
            </p>
          </div>
        ) : analysisData && analysisData.route_analysis ? (
          <div className="space-y-6">
            <RouteAnalysisCard analysis={analysisData.route_analysis} />
          </div>
        ) : (
          <div className="space-y-4 py-20 text-center">
            <p className="text-secondary">{analysisModalText.empty}</p>
            <Button
              onClick={onAnalyze}
              className="h-10 rounded-lg px-8 font-bold"
            >
              {analysisModalText.actions.start}
            </Button>
          </div>
        )}

        <div className="mt-4 flex flex-wrap justify-end gap-3 border-t border-border pt-6">
          <Button
            variant="secondary"
            onClick={() => setIsCalibrationOpen(true)}
            className="h-10 gap-2 rounded-lg px-6"
          >
            <Crosshair className="h-4 w-4" />
            {analysisModalText.actions.calibrate}
          </Button>
          <Button
            variant="secondary"
            onClick={onClose}
            className="h-10 rounded-lg px-6"
          >
            {analysisModalText.actions.close}
          </Button>
          {!isLoading && analysisData ? (
            <Button onClick={onAnalyze} className="h-10 rounded-lg px-6">
              {analysisModalText.actions.rerun}
            </Button>
          ) : null}
        </div>
      </div>

      <CalibrationModal
        isOpen={isCalibrationOpen}
        onClose={() => setIsCalibrationOpen(false)}
        routeLabel={`${location.cikis_yeri} → ${location.varis_yeri}`}
      />
    </Modal>
  );
}
