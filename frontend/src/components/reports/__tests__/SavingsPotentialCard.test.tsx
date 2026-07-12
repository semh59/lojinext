import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "../../../test/test-utils";

vi.mock("../../../api/reports", () => ({
  reportService: {
    getSavingsPotential: vi.fn(),
  },
}));

import { reportService } from "../../../api/reports";
import { SavingsPotentialCard } from "../SavingsPotentialCard";

describe("SavingsPotentialCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("aylık + yıllık tasarrufu ve % iyileşmeyi gösterir", async () => {
    // Regression: potential_savings backend'de 90-günlük (sabit) bir
    // toplamdır (calculate_savings_potential'ın penceresi) — pickMonthly()
    // bunu 3'e bölmeden doğrudan "Aylık Potansiyel" olarak gösteriyordu,
    // gerçek aylık değerin ~3 katını yanlış etiketle sunuyordu.
    (
      reportService.getSavingsPotential as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      current_consumption: 35,
      target_consumption: 30,
      current_cost: 10000,
      target_cost: 8500,
      potential_savings: 1500, // 90-günlük toplam → aylık 500 olmalı
      annual_projection: 18000,
      savings_percentage: 15,
    });

    render(<SavingsPotentialCard />);

    await waitFor(() =>
      expect(screen.getByText("Aylık Potansiyel")).toBeInTheDocument(),
    );
    expect(screen.getByText("15.0%")).toBeInTheDocument();
    // Currency Turkish format ₺ with optional thousands separator
    expect(screen.getByText(/₺?\s?500\b/)).toBeInTheDocument();
    expect(screen.queryByText(/1\.?500/)).not.toBeInTheDocument();
    expect(screen.getByText(/18\.?000/)).toBeInTheDocument();
    // Mevcut ortalama
    expect(screen.getByText(/35\.0 L\/100km/)).toBeInTheDocument();
  });

  it("slider değişimi yeni target ile servis çağrısı tetikler", async () => {
    const fn = reportService.getSavingsPotential as ReturnType<typeof vi.fn>;
    fn.mockResolvedValue({ potential_savings: 0, savings_percentage: 0 });

    render(<SavingsPotentialCard />);
    await waitFor(() => expect(fn).toHaveBeenCalled());
    const initialCall = fn.mock.calls[0][0];
    expect(initialCall).toBe(30);

    const slider = screen.getByLabelText("Hedef tüketim") as HTMLInputElement;
    fireEvent.change(slider, { target: { value: "25" } });
    await waitFor(() => expect(fn).toHaveBeenCalledWith(25));
  });

  it("409 conflict → yetersiz veri uyarısı", async () => {
    const err: any = new Error("insufficient data");
    err.response = { status: 409 };
    (
      reportService.getSavingsPotential as ReturnType<typeof vi.fn>
    ).mockRejectedValue(err);
    render(<SavingsPotentialCard />);
    await waitFor(() =>
      expect(
        screen.getByText(/Gerçek maliyet verisi henüz yeterli değil/),
      ).toBeInTheDocument(),
    );
  });
});
