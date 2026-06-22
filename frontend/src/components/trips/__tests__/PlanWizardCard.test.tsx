import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "../../../test/test-utils";
import { PlanWizardCard } from "../PlanWizardCard";
import type {
  DriverSuggestion,
  VehicleSuggestion,
} from "../../../api/trip-planner";

const baseVehicle: VehicleSuggestion = {
  arac_id: 12,
  plaka: "34 ABC 123",
  yas: 4,
  score: 0.82,
  predicted_liters: 142.3,
  fuel_score: 0.95,
  route_history_score: 0.8,
  vehicle_health_score: 0.84,
  availability_score: 0.71,
  similar_trip_count: 4,
  cold_start: false,
  reasons: ["Aday seti içinde düşük tahmini tüketim"],
};

const baseDriver: DriverSuggestion = {
  sofor_id: 7,
  ad_soyad: "Ali Veli",
  score: 0.78,
  route_type_perf: 0.85,
  overall_hybrid: 0.72,
  availability_score: 0.71,
  route_type: "highway_dominant",
  deviation_pct: -4.5,
  cold_start: false,
  reasons: ["Bu güzergah tipinde tutarlı performans"],
};

describe("PlanWizardCard", () => {
  it("vehicle kind → plaka + tahmini tüketim + skor görünür", () => {
    render(
      <PlanWizardCard
        kind="vehicle"
        data={baseVehicle}
        selected={false}
        onSelect={() => {}}
        onOpenXai={() => {}}
      />,
    );
    expect(screen.getByText("34 ABC 123")).toBeInTheDocument();
    expect(screen.getByText(/142\.3/)).toBeInTheDocument();
    expect(screen.getByText("82")).toBeInTheDocument(); // score=0.82→82
  });

  it("driver kind → ad_soyad + sapma % + hibrit skor", () => {
    render(
      <PlanWizardCard
        kind="driver"
        data={baseDriver}
        selected={false}
        onSelect={() => {}}
        onOpenXai={() => {}}
      />,
    );
    expect(screen.getByText("Ali Veli")).toBeInTheDocument();
    expect(screen.getByText("-4.5%")).toBeInTheDocument();
    expect(screen.getByText("72/100")).toBeInTheDocument();
  });

  it('selected=true → "Seçildi" rozeti + aria-pressed', () => {
    render(
      <PlanWizardCard
        kind="vehicle"
        data={baseVehicle}
        selected={true}
        onSelect={() => {}}
        onOpenXai={() => {}}
      />,
    );
    expect(screen.getByText("Seçildi")).toBeInTheDocument();
    const btn = screen.getAllByRole("button")[0];
    expect(btn).toHaveAttribute("aria-pressed", "true");
  });

  it('cold_start=true → "Yeni araç" rozeti', () => {
    render(
      <PlanWizardCard
        kind="vehicle"
        data={{ ...baseVehicle, cold_start: true }}
        selected={false}
        onSelect={() => {}}
        onOpenXai={() => {}}
      />,
    );
    expect(screen.getByText("Yeni araç")).toBeInTheDocument();
  });

  it("kart tıklama → onSelect; XAI butonu tıklama → onOpenXai (propagation engellenir)", () => {
    const onSelect = vi.fn();
    const onOpenXai = vi.fn();
    render(
      <PlanWizardCard
        kind="vehicle"
        data={baseVehicle}
        selected={false}
        onSelect={onSelect}
        onOpenXai={onOpenXai}
      />,
    );
    fireEvent.click(screen.getByText("Neden bu?"));
    expect(onOpenXai).toHaveBeenCalledTimes(1);
    expect(onSelect).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText("34 ABC 123"));
    expect(onSelect).toHaveBeenCalledTimes(1);
  });
});
