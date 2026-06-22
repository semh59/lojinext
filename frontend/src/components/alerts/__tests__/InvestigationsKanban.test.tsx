import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/investigations", () => ({
  investigationService: {
    list: vi.fn(),
    get: vi.fn(),
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
import { InvestigationsKanban } from "../InvestigationsKanban";

describe("InvestigationsKanban", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("boş liste → emptyKanban mesajı", async () => {
    (investigationService.list as ReturnType<typeof vi.fn>).mockResolvedValue(
      [],
    );
    render(<InvestigationsKanban />);
    await waitFor(() =>
      expect(screen.getByText("Henüz soruşturma yok.")).toBeInTheDocument(),
    );
  });

  it("iki kart farklı kolonlarda görünür", async () => {
    (investigationService.list as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
        id: 1,
        anomaly_id: 10,
        status: "open",
        suspicion_score: 0.5,
        suspicion_level: "medium",
        assigned_to_user_id: null,
        notes: null,
        resolution_type: null,
        evidence_files: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        closed_at: null,
        plaka: "34 AAA 11",
        sofor_adi: "Şoför A",
        sapma_yuzde: 20,
      },
      {
        id: 2,
        anomaly_id: 11,
        status: "investigating",
        suspicion_score: 0.7,
        suspicion_level: "high",
        assigned_to_user_id: 5,
        notes: null,
        resolution_type: null,
        evidence_files: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        closed_at: null,
        plaka: "34 BBB 22",
        sofor_adi: "Şoför B",
        sapma_yuzde: 40,
      },
    ]);
    render(<InvestigationsKanban />);
    await waitFor(() =>
      expect(screen.getByText("34 AAA 11")).toBeInTheDocument(),
    );
    expect(screen.getByText("34 BBB 22")).toBeInTheDocument();
    expect(
      screen.getByText("Yakıt Hırsızlığı Soruşturmaları"),
    ).toBeInTheDocument();
  });
});
