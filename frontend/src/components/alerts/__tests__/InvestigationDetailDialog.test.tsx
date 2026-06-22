import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "../../../test/test-utils";

vi.mock("../../../api/investigations", () => ({
  investigationService: {
    get: vi.fn(),
    update: vi.fn(),
    close: vi.fn(),
  },
}));

vi.mock("../../../context/NotificationContext", async () => {
  const actual: any = await vi.importActual(
    "../../../context/NotificationContext",
  );
  return {
    ...actual,
    useNotify: () => ({ notify: vi.fn() }),
  };
});

import { investigationService } from "../../../api/investigations";
import { InvestigationDetailDialog } from "../InvestigationDetailDialog";

const buildInv = (overrides: Partial<any> = {}) => ({
  id: 42,
  anomaly_id: 7,
  status: "open",
  suspicion_score: 0.55,
  suspicion_level: "medium",
  assigned_to_user_id: null,
  notes: null,
  resolution_type: null,
  evidence_files: [],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  closed_at: null,
  plaka: "34 ABC 999",
  sofor_adi: "Ali Veli",
  sapma_yuzde: 22.0,
  ...overrides,
});

describe("InvestigationDetailDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("investigationId=null → render etmez", () => {
    const { container } = render(
      <InvestigationDetailDialog investigationId={null} onClose={() => {}} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("açık soruşturma → detaylar görünür", async () => {
    (investigationService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      buildInv(),
    );
    render(
      <InvestigationDetailDialog investigationId={42} onClose={() => {}} />,
    );
    await waitFor(() =>
      expect(screen.getByText(/34 ABC 999/)).toBeInTheDocument(),
    );
    expect(screen.getByText("Soruşturma #42")).toBeInTheDocument();
    // Save butonu
    expect(screen.getByRole("button", { name: /Kaydet/i })).toBeEnabled();
  });

  it('closed durum → "değişiklik yapılamaz" uyarısı', async () => {
    (investigationService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      buildInv({ status: "closed" }),
    );
    render(
      <InvestigationDetailDialog investigationId={42} onClose={() => {}} />,
    );
    await waitFor(() =>
      expect(
        screen.getByText("Bu soruşturma kapatıldı; değişiklik yapılamaz."),
      ).toBeInTheDocument(),
    );
  });

  it("X butonu → onClose tetiklenir", async () => {
    (investigationService.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      buildInv(),
    );
    const onClose = vi.fn();
    render(
      <InvestigationDetailDialog investigationId={42} onClose={onClose} />,
    );
    await waitFor(() => screen.getByText(/34 ABC 999/));
    fireEvent.click(screen.getByLabelText("Kapat"));
    expect(onClose).toHaveBeenCalled();
  });
});
