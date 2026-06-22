import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "../../../test/test-utils";
import { PlanWizardXaiPanel } from "../PlanWizardXaiPanel";
import type {
  DriverSuggestion,
  VehicleSuggestion,
} from "../../../api/trip-planner";

const baseVehicle: VehicleSuggestion = {
  arac_id: 12,
  plaka: "34 ABC 123",
  yas: 4,
  score: 0.812,
  predicted_liters: 142.3,
  fuel_score: 0.95,
  route_history_score: 0.8,
  vehicle_health_score: 0.84,
  availability_score: 0.71,
  similar_trip_count: 4,
  cold_start: false,
  reasons: [
    "Aday seti içinde düşük tahmini tüketim",
    "⚠ Son haftada yoğun kullanım",
  ],
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

describe("PlanWizardXaiPanel", () => {
  it("item=null → render etmez", () => {
    const { container } = render(
      <PlanWizardXaiPanel item={null} kind={null} onClose={() => {}} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("vehicle item → plaka, total skor, alt skor barları + meta görünür", () => {
    render(
      <PlanWizardXaiPanel
        item={baseVehicle}
        kind="vehicle"
        onClose={() => {}}
      />,
    );
    expect(screen.getByText("34 ABC 123")).toBeInTheDocument();
    // Toplam skor 0.81 formatlı görünür
    expect(screen.getByText("0.81")).toBeInTheDocument();
    // Araç-özel alanlar
    expect(screen.getByText("Yakıt verimliliği")).toBeInTheDocument();
    expect(screen.getByText("Güzergah tarihi")).toBeInTheDocument();
    expect(screen.getByText("Araç sağlığı")).toBeInTheDocument();
    // Meta
    expect(screen.getByText("142.3 L")).toBeInTheDocument();
    // yas=4 ve similar_trip_count=4 — iki ayrı element, ikisi de mevcut
    expect(screen.getAllByText("4").length).toBeGreaterThanOrEqual(2);
  });

  it("driver item → şoför adı + driver alt skorları + sapma % yeşil", () => {
    render(
      <PlanWizardXaiPanel item={baseDriver} kind="driver" onClose={() => {}} />,
    );
    expect(screen.getByText("Ali Veli")).toBeInTheDocument();
    expect(screen.getByText("Güzergah tipi performansı")).toBeInTheDocument();
    expect(screen.getByText("Hibrit skor")).toBeInTheDocument();
    expect(screen.getByText("-4.5%")).toBeInTheDocument();
    expect(screen.getByText("Otoyol Ağırlıklı")).toBeInTheDocument();
  });

  it("uyarı reasons (⚠ ile başlayan) sarı renkte, normal reasons standart", () => {
    render(
      <PlanWizardXaiPanel
        item={baseVehicle}
        kind="vehicle"
        onClose={() => {}}
      />,
    );
    // ⚠ prefix kaldırılmış metin görünmeli
    expect(screen.getByText("Son haftada yoğun kullanım")).toBeInTheDocument();
    // Normal reason aynen
    expect(
      screen.getByText("Aday seti içinde düşük tahmini tüketim"),
    ).toBeInTheDocument();
  });

  it('reasons boş → "Sebep listesi boş" mesajı', () => {
    render(
      <PlanWizardXaiPanel
        item={{ ...baseVehicle, reasons: [] }}
        kind="vehicle"
        onClose={() => {}}
      />,
    );
    expect(screen.getByText("Sebep listesi boş.")).toBeInTheDocument();
  });

  it("X butonu → onClose tetiklenir", () => {
    const onClose = vi.fn();
    render(
      <PlanWizardXaiPanel
        item={baseVehicle}
        kind="vehicle"
        onClose={onClose}
      />,
    );
    fireEvent.click(screen.getByLabelText("Kapat"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("backdrop click → onClose; iç dialog click → onClose çağrılmaz", () => {
    const onClose = vi.fn();
    render(
      <PlanWizardXaiPanel
        item={baseVehicle}
        kind="vehicle"
        onClose={onClose}
      />,
    );
    // Backdrop dış div (role="presentation")
    const backdrop = screen.getByRole("presentation");
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);

    // İç dialog click event'i stopPropagation
    onClose.mockClear();
    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose).not.toHaveBeenCalled();
  });
});
