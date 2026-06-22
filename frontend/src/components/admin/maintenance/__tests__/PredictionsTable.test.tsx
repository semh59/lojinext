import { describe, expect, it, vi, beforeEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
} from "../../../../test/test-utils";

vi.mock("../../../../api/maintenance-predictions", () => ({
  maintenancePredictionsService: {
    getAll: vi.fn(),
    getForArac: vi.fn(),
    downloadIcs: vi.fn(),
  },
}));

vi.mock("../../../../context/NotificationContext", async () => {
  const actual: any = await vi.importActual(
    "../../../../context/NotificationContext",
  );
  return { ...actual, useNotify: () => ({ notify: vi.fn() }) };
});

import { maintenancePredictionsService } from "../../../../api/maintenance-predictions";
import { PredictionsTable } from "../PredictionsTable";

const overdue = {
  arac_id: 1,
  plaka: "34 ABC 111",
  bakim_tipi: "PERIYODIK",
  predictable: true,
  predicted_date: "2026-05-10",
  days_remaining: -16,
  is_overdue: true,
  confidence: 0.85,
  risk_level: "overdue" as const,
  savings_pct: 5.5,
  reasons: ["GECİKMİŞ — derhal planlanmalı", "Son PERIYODIK 400 gün önce"],
};

const soon = {
  arac_id: 2,
  plaka: "34 DEF 222",
  bakim_tipi: "PERIYODIK",
  predictable: true,
  predicted_date: "2026-06-05",
  days_remaining: 10,
  is_overdue: false,
  confidence: 0.72,
  risk_level: "soon" as const,
  savings_pct: 0,
  reasons: ["Tahmini 800 km kaldı"],
};

const unpredictable = {
  arac_id: 3,
  plaka: "34 GHI 333",
  bakim_tipi: "PERIYODIK",
  predictable: false,
  predicted_date: null,
  days_remaining: null,
  is_overdue: false,
  confidence: 0.5,
  risk_level: "low" as const,
  savings_pct: 0,
  reasons: ["Yeterli veri yok (bakım geçmişi veya kullanım eksik)"],
};

describe("PredictionsTable", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('boş veri → "Henüz tahmin edilebilir bakım yok" mesajı', async () => {
    (
      maintenancePredictionsService.getAll as ReturnType<typeof vi.fn>
    ).mockResolvedValue([]);
    render(<PredictionsTable />);
    await waitFor(() =>
      expect(
        screen.getByText(/Henüz tahmin edilebilir bakım yok/),
      ).toBeInTheDocument(),
    );
  });

  it("3 araç → satırlar render edilir, overdue önce (sıralama)", async () => {
    (
      maintenancePredictionsService.getAll as ReturnType<typeof vi.fn>
    ).mockResolvedValue([unpredictable, soon, overdue]);
    render(<PredictionsTable />);
    await waitFor(() => screen.getByText("34 ABC 111"));

    const rows = screen.getAllByRole("row");
    // Header + 3 data row
    expect(rows.length).toBe(4);
    // İlk veri satırı overdue araç olmalı (sıralı)
    expect(rows[1].textContent).toContain("34 ABC 111");
    // Son veri satırı unpredictable olmalı
    expect(rows[3].textContent).toContain("34 GHI 333");
  });

  it('overdue araç için "Gecikmiş" rozeti + negatif gün gösterilir', async () => {
    (
      maintenancePredictionsService.getAll as ReturnType<typeof vi.fn>
    ).mockResolvedValue([overdue]);
    render(<PredictionsTable />);
    await waitFor(() => screen.getByText("34 ABC 111"));
    expect(screen.getByText("Gecikmiş")).toBeInTheDocument();
    expect(screen.getByText("-16")).toBeInTheDocument();
    // Tasarruf %5.5 görünür
    expect(screen.getByText("%5.5")).toBeInTheDocument();
  });

  it('unpredictable araç için "Tahmin için yetersiz veri" yazısı', async () => {
    (
      maintenancePredictionsService.getAll as ReturnType<typeof vi.fn>
    ).mockResolvedValue([unpredictable]);
    render(<PredictionsTable />);
    await waitFor(() =>
      expect(screen.getByText("Tahmin için yetersiz veri")).toBeInTheDocument(),
    );
  });

  it("satıra tıklayınca drawer açılır", async () => {
    (
      maintenancePredictionsService.getAll as ReturnType<typeof vi.fn>
    ).mockResolvedValue([overdue]);
    render(<PredictionsTable />);
    await waitFor(() => screen.getByText("34 ABC 111"));
    fireEvent.click(screen.getByText("34 ABC 111"));
    // Drawer header görünür
    expect(
      await screen.findByText("GECİKMİŞ — derhal planlanmalı"),
    ).toBeInTheDocument();
  });
});
