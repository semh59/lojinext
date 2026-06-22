import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/trip-planner", () => ({
  tripPlannerService: {
    plan: vi.fn(),
  },
}));

import { tripPlannerService } from "../../../api/trip-planner";
import { PlanWizardStep } from "../PlanWizardStep";

const okResult = {
  weather_impact: 1.07,
  risk_label: "medium" as const,
  route_type: "highway_dominant" as const,
  vehicles: [
    {
      arac_id: 1,
      plaka: "34 AAA 111",
      yas: 3,
      score: 0.9,
      predicted_liters: 120,
      fuel_score: 1.0,
      route_history_score: 0.8,
      vehicle_health_score: 0.9,
      availability_score: 0.8,
      similar_trip_count: 4,
      cold_start: false,
      reasons: ["Aday seti içinde düşük tahmini tüketim"],
    },
  ],
  drivers: [
    {
      sofor_id: 100,
      ad_soyad: "Ali Veli",
      score: 0.85,
      route_type_perf: 0.9,
      overall_hybrid: 0.8,
      availability_score: 0.7,
      route_type: "highway_dominant" as const,
      deviation_pct: -5,
      cold_start: false,
      reasons: ["Bu güzergah tipinde tutarlı performans"],
    },
  ],
  generated_at: new Date().toISOString(),
  cache_hit: false,
};

const validPayload = {
  tarih: "2026-06-15",
  guzergah_id: 42,
  cikis_yeri: "Ankara",
  varis_yeri: "İstanbul",
  mesafe_km: 450,
  ascent_m: 320,
  descent_m: 310,
  flat_distance_km: 400,
  weight_kg: 22000,
  top_n: 3,
};

describe("PlanWizardStep", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('payload yok → "Önce tarih..." uyarısı + buton disabled', () => {
    render(<PlanWizardStep payload={null} onSelectAndContinue={() => {}} />);
    expect(
      screen.getByText(/Önce tarih ve güzergah seçin/),
    ).toBeInTheDocument();
    const fetchBtn = screen.getByRole("button", {
      name: /Önerileri Getir/,
    });
    expect(fetchBtn).toBeDisabled();
  });

  it("payload var → fetch tıklanır, sonuçlar render edilir, plan() doğru payload ile çağrılır", async () => {
    (tripPlannerService.plan as ReturnType<typeof vi.fn>).mockResolvedValue(
      okResult,
    );
    render(
      <PlanWizardStep payload={validPayload} onSelectAndContinue={() => {}} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Önerileri Getir/ }));
    await waitFor(() =>
      expect(screen.getByText("34 AAA 111")).toBeInTheDocument(),
    );
    expect(screen.getByText("Ali Veli")).toBeInTheDocument();
    expect(tripPlannerService.plan).toHaveBeenCalledWith(validPayload);
    expect(screen.getByText(/Hava: Orta risk/)).toBeInTheDocument();
    expect(screen.getByText("Otoyol Ağırlıklı")).toBeInTheDocument();
  });

  it('seçim yapılmadan "Seç ve Devam" disabled; her ikisi seçildiğinde aktif olur ve onSelectAndContinue çağrılır', async () => {
    (tripPlannerService.plan as ReturnType<typeof vi.fn>).mockResolvedValue(
      okResult,
    );
    const onSelect = vi.fn();
    render(
      <PlanWizardStep payload={validPayload} onSelectAndContinue={onSelect} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Önerileri Getir/ }));
    await waitFor(() => screen.getByText("34 AAA 111"));

    const continueBtn = screen.getByRole("button", {
      name: /Seç ve Devam/,
    });
    expect(continueBtn).toBeDisabled();

    // Önce araç seç
    fireEvent.click(screen.getByText("34 AAA 111"));
    expect(continueBtn).toBeDisabled(); // şoför yok

    // Sonra şoför seç
    fireEvent.click(screen.getByText("Ali Veli"));
    expect(continueBtn).toBeEnabled();

    fireEvent.click(continueBtn);
    expect(onSelect).toHaveBeenCalledWith({
      arac_id: 1,
      sofor_id: 100,
      plaka: "34 AAA 111",
      sofor_adi: "Ali Veli",
    });
  });

  it('boş sonuç → "aday bulunamadı" mesajı', async () => {
    (tripPlannerService.plan as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...okResult,
      vehicles: [],
      drivers: [],
    });
    render(
      <PlanWizardStep payload={validPayload} onSelectAndContinue={() => {}} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Önerileri Getir/ }));
    await waitFor(() =>
      expect(screen.getByText(/uygun aday bulunamadı/)).toBeInTheDocument(),
    );
  });

  it("503 hatası → flagOff mesajı; retry butonu görünür", async () => {
    (tripPlannerService.plan as ReturnType<typeof vi.fn>).mockRejectedValue({
      response: { status: 503, data: {} },
    });
    render(
      <PlanWizardStep payload={validPayload} onSelectAndContinue={() => {}} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Önerileri Getir/ }));
    await waitFor(() =>
      expect(screen.getByText(/sihirbazı devre dışı/)).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: /Tekrar Dene/ }),
    ).toBeInTheDocument();
  });
});
