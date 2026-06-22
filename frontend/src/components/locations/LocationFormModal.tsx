import { Info, MapIcon, Search } from "lucide-react";

import { locationFormText } from "../../resources/tr/locations";
import { GeocodeSuggestion } from "../../api/locations";
import { Location, LocationCreate } from "../../types/location";
import {
  formatCoordinate,
  formatDuration,
  useLocationForm,
} from "../../hooks/useLocationForm";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Modal } from "../ui/Modal";

interface LocationFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: LocationCreate) => Promise<void>;
  location: Location | null;
}

export const LocationFormModal = ({
  isOpen,
  onClose,
  onSave,
  location,
}: LocationFormModalProps) => {
  const {
    register,
    handleSubmit,
    errors,
    isSubmitting,
    onSubmit,
    isCalculating,
    routeAnalysisData,
    searchText,
    suggestions,
    loadingSuggestions,
    watchedDuration,
    originLat,
    originLon,
    destinationLat,
    destinationLon,
    calculateRouteKey,
    handleSearchInputChange,
    handleSuggestionSelect,
    handleCalculate,
  } = useLocationForm({ isOpen, location, onSave, onClose });

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        location ? locationFormText.titles.edit : locationFormText.titles.create
      }
      size="lg"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6" noValidate>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className="space-y-4">
            <div className="flex items-center gap-2 px-1">
              <MapIcon className="h-4 w-4 text-accent" />
              <h3 className="text-xs font-bold uppercase tracking-widest text-primary">
                {locationFormText.sections.points}
              </h3>
            </div>

            <div className="space-y-2">
              <Input
                aria-label={locationFormText.inputs.originSearchLabel}
                value={searchText.cikis}
                onChange={handleSearchInputChange("cikis")}
                placeholder={locationFormText.inputs.originPlaceholder}
                error={
                  !!errors.cikis_yeri ||
                  !!errors.cikis_lat ||
                  !!errors.cikis_lon
                }
              />
              {loadingSuggestions.cikis ? (
                <p className="px-1 text-xs text-secondary">
                  {locationFormText.inputs.searching}
                </p>
              ) : null}
              {suggestions.cikis.length > 0 ? (
                <div className="rounded-xl border border-border bg-surface p-2">
                  {suggestions.cikis.map((suggestion: GeocodeSuggestion) => (
                    <button
                      key={`cikis-${suggestion.label}-${suggestion.lat}-${suggestion.lon}`}
                      type="button"
                      onClick={() =>
                        handleSuggestionSelect("cikis", suggestion)
                      }
                      className="flex w-full items-start gap-2 rounded-lg px-3 py-2 text-left text-sm text-primary transition-colors hover:bg-elevated"
                    >
                      <Search className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
                      <span>{suggestion.label}</span>
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="space-y-2">
              <Input
                aria-label={locationFormText.inputs.destinationSearchLabel}
                value={searchText.varis}
                onChange={handleSearchInputChange("varis")}
                placeholder={locationFormText.inputs.destinationPlaceholder}
                error={
                  !!errors.varis_yeri ||
                  !!errors.varis_lat ||
                  !!errors.varis_lon
                }
              />
              {loadingSuggestions.varis ? (
                <p className="px-1 text-xs text-secondary">
                  {locationFormText.inputs.searching}
                </p>
              ) : null}
              {suggestions.varis.length > 0 ? (
                <div className="rounded-xl border border-border bg-surface p-2">
                  {suggestions.varis.map((suggestion: GeocodeSuggestion) => (
                    <button
                      key={`varis-${suggestion.label}-${suggestion.lat}-${suggestion.lon}`}
                      type="button"
                      onClick={() =>
                        handleSuggestionSelect("varis", suggestion)
                      }
                      className="flex w-full items-start gap-2 rounded-lg px-3 py-2 text-left text-sm text-primary transition-colors hover:bg-elevated"
                    >
                      <Search className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
                      <span>{suggestion.label}</span>
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="grid grid-cols-2 gap-3 rounded-card border border-border bg-elevated/40 p-4">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-widest text-secondary">
                  {locationFormText.inputs.originCoordinates}
                </p>
                <p className="mt-2 font-mono text-xs text-primary">
                  {formatCoordinate(originLat)}, {formatCoordinate(originLon)}
                </p>
              </div>
              <div>
                <p className="text-[11px] font-bold uppercase tracking-widest text-secondary">
                  {locationFormText.inputs.destinationCoordinates}
                </p>
                <p className="mt-2 font-mono text-xs text-primary">
                  {formatCoordinate(destinationLat)},{" "}
                  {formatCoordinate(destinationLon)}
                </p>
              </div>
            </div>

            <Button
              type="button"
              className="w-full"
              onClick={handleCalculate}
              isLoading={isCalculating}
              disabled={!calculateRouteKey}
            >
              {locationFormText.inputs.recalculate}
            </Button>
          </div>

          <div className="space-y-4">
            <div className="flex items-center gap-2 px-1">
              <Info className="h-4 w-4 text-accent" />
              <h3 className="text-xs font-bold uppercase tracking-widest text-primary">
                {locationFormText.sections.summary}
              </h3>
            </div>

            <Input
              aria-label={locationFormText.inputs.distanceLabel}
              type="number"
              step="any"
              readOnly
              className="bg-elevated font-black text-primary"
              error={!!errors.mesafe_km}
              {...register("mesafe_km", { valueAsNumber: true })}
            />
            <Input
              aria-label={locationFormText.inputs.durationLabel}
              value={formatDuration(watchedDuration)}
              readOnly
              className="bg-elevated font-black text-primary"
            />

            <div className="grid grid-cols-2 gap-3">
              <Input
                aria-label={locationFormText.inputs.ascentLabel}
                type="number"
                readOnly
                className="bg-elevated"
                {...register("ascent_m", { valueAsNumber: true })}
              />
              <Input
                aria-label={locationFormText.inputs.descentLabel}
                type="number"
                readOnly
                className="bg-elevated"
                {...register("descent_m", { valueAsNumber: true })}
              />
            </div>

            {routeAnalysisData ? (
              <div className="rounded-card border border-border bg-elevated/40 p-4">
                <p className="text-[11px] font-bold uppercase tracking-widest text-secondary">
                  {locationFormText.inputs.distributionTitle}
                </p>
                <div className="mt-3 grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="font-bold text-primary">
                      {locationFormText.inputs.highway}
                    </p>
                    <p className="text-secondary">
                      {(
                        (routeAnalysisData.highway?.flat || 0) +
                        (routeAnalysisData.highway?.up || 0) +
                        (routeAnalysisData.highway?.down || 0)
                      ).toFixed(1)}{" "}
                      km
                    </p>
                  </div>
                  <div>
                    <p className="font-bold text-primary">
                      {locationFormText.inputs.otherRoads}
                    </p>
                    <p className="text-secondary">
                      {(
                        (routeAnalysisData.other?.flat || 0) +
                        (routeAnalysisData.other?.up || 0) +
                        (routeAnalysisData.other?.down || 0)
                      ).toFixed(1)}{" "}
                      km
                    </p>
                  </div>
                </div>
              </div>
            ) : null}

            <textarea
              {...register("notlar")}
              className="min-h-[100px] w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-primary outline-none transition-all focus:border-accent focus:ring-2 focus:ring-accent/5"
              placeholder={locationFormText.inputs.notesPlaceholder}
            />
          </div>
        </div>

        <div className="hidden">
          <input {...register("cikis_yeri")} />
          <input {...register("varis_yeri")} />
          <input
            type="number"
            {...register("tahmini_sure_saat", { valueAsNumber: true })}
          />
          <input {...register("zorluk")} />
          <input
            type="number"
            {...register("flat_distance_km", { valueAsNumber: true })}
          />
          <input
            type="number"
            {...register("otoban_mesafe_km", { valueAsNumber: true })}
          />
          <input
            type="number"
            {...register("sehir_ici_mesafe_km", { valueAsNumber: true })}
          />
          <input
            type="number"
            {...register("cikis_lat", { valueAsNumber: true })}
          />
          <input
            type="number"
            {...register("cikis_lon", { valueAsNumber: true })}
          />
          <input
            type="number"
            {...register("varis_lat", { valueAsNumber: true })}
          />
          <input
            type="number"
            {...register("varis_lon", { valueAsNumber: true })}
          />
        </div>

        <div className="flex justify-end gap-3 border-t border-border pt-6">
          <Button variant="secondary" type="button" onClick={onClose}>
            {locationFormText.actions.cancel}
          </Button>
          <Button
            type="submit"
            isLoading={isSubmitting}
            disabled={isCalculating}
          >
            {location
              ? locationFormText.actions.update
              : locationFormText.actions.save}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
