/**
 * 0-mock epiği re-triage (maintenance domain): NOT converted — purely
 * presentational from the test's point of view. Every test drives the
 * component via props only (`prediction`/`onClose`); none of them exercise
 * `handleDownload` (the only path that calls
 * `maintenancePredictionsService.downloadIcs`), so the mocked service call
 * is inert here — there is no real HTTP boundary actually under test.
 * Converting would add a real backend dependency with zero assertion
 * gain. Left mocked (same category as the RouteAnalysisCard/
 * RouteProfileChart files from Faz 2, which needed no changes).
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "../../../../test/test-utils";

vi.mock("../../../../api/maintenance-predictions", () => ({
  maintenancePredictionsService: {
    downloadIcs: vi.fn(),
  },
}));

vi.mock("../../../../context/NotificationContext", async () => {
  const actual: any = await vi.importActual(
    "../../../../context/NotificationContext",
  );
  return { ...actual, useNotify: () => ({ notify: vi.fn() }) };
});

import { MaintenanceDetailDrawer } from "../MaintenanceDetailDrawer";

const predictable = {
  arac_id: 12,
  plaka: "34 ABC 123",
  bakim_tipi: "PERIYODIK",
  predictable: true,
  predicted_date: "2026-06-15",
  days_remaining: 14,
  is_overdue: false,
  confidence: 0.84,
  risk_level: "soon" as const,
  savings_pct: 5.5,
  reasons: ["Tüketim trendi %+12 → 8 gün erkene alındı"],
};

const unpredictable = {
  arac_id: 99,
  plaka: "34 X 1",
  bakim_tipi: "PERIYODIK",
  predictable: false,
  predicted_date: null,
  days_remaining: null,
  is_overdue: false,
  confidence: 0.5,
  risk_level: "low" as const,
  savings_pct: 0,
  reasons: ["Yeterli veri yok"],
};

describe("MaintenanceDetailDrawer", () => {
  it("prediction=null → render etmez", () => {
    const { container } = render(
      <MaintenanceDetailDrawer prediction={null} onClose={() => {}} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("predictable=true → tarih + gün + güven + tasarruf alanları görünür", () => {
    render(
      <MaintenanceDetailDrawer prediction={predictable} onClose={() => {}} />,
    );
    expect(screen.getByText("34 ABC 123")).toBeInTheDocument();
    expect(screen.getByText("15.06.2026")).toBeInTheDocument();
    expect(screen.getByText("14 gün")).toBeInTheDocument();
    expect(screen.getByText("84%")).toBeInTheDocument();
    expect(screen.getByText("%5.5")).toBeInTheDocument();
    // İndirme butonu görünür
    expect(
      screen.getByRole("button", { name: /Takvime İndir/ }),
    ).toBeInTheDocument();
  });

  it('predictable=false → "veri yok" mesajı + indirme butonu gizli', () => {
    render(
      <MaintenanceDetailDrawer prediction={unpredictable} onClose={() => {}} />,
    );
    expect(screen.getByText(/yeterli veri yok/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Takvime İndir/ }),
    ).not.toBeInTheDocument();
  });

  it("X butonu → onClose çağrılır", () => {
    const onClose = vi.fn();
    render(
      <MaintenanceDetailDrawer prediction={predictable} onClose={onClose} />,
    );
    fireEvent.click(screen.getByLabelText("Kapat"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("backdrop click → onClose; dialog click → çağrılmaz", () => {
    const onClose = vi.fn();
    render(
      <MaintenanceDetailDrawer prediction={predictable} onClose={onClose} />,
    );
    const backdrop = screen.getByRole("presentation");
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);

    onClose.mockClear();
    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("GECİKMİŞ reason satırı kırmızı kart olarak görünür", () => {
    const overdue = {
      ...predictable,
      is_overdue: true,
      days_remaining: -5,
      risk_level: "overdue" as const,
      reasons: ["GECİKMİŞ — derhal planlanmalı"],
    };
    render(<MaintenanceDetailDrawer prediction={overdue} onClose={() => {}} />);
    expect(
      screen.getByText("GECİKMİŞ — derhal planlanmalı"),
    ).toBeInTheDocument();
  });
});
