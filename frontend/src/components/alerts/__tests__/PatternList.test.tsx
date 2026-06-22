import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/investigations", () => ({
  investigationService: {
    getPatterns: vi.fn(),
  },
}));

import { investigationService } from "../../../api/investigations";
import { PatternList } from "../PatternList";

describe("PatternList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('boş döndüğünde "bulunamadı" mesajı', async () => {
    (
      investigationService.getPatterns as ReturnType<typeof vi.fn>
    ).mockResolvedValue([]);
    render(<PatternList />);
    await waitFor(() =>
      expect(
        screen.getByText("Tekrarlayan örüntü bulunamadı."),
      ).toBeInTheDocument(),
    );
  });

  it("iki pattern → tablo satırlarda görünür", async () => {
    (
      investigationService.getPatterns as ReturnType<typeof vi.fn>
    ).mockResolvedValue([
      {
        sofor_id: 1,
        sofor_adi: "Ali Veli",
        arac_id: 2,
        plaka: "34 ABC 11",
        occurrence_count: 4,
        avg_suspicion_score: 0.72,
        last_seen: "2026-05-22T10:00:00Z",
      },
      {
        sofor_id: 2,
        sofor_adi: "Mehmet Demir",
        arac_id: 3,
        plaka: "34 XYZ 99",
        occurrence_count: 3,
        avg_suspicion_score: 0.65,
        last_seen: "2026-05-21T10:00:00Z",
      },
    ]);
    render(<PatternList />);
    await waitFor(() =>
      expect(screen.getByText("Ali Veli")).toBeInTheDocument(),
    );
    expect(screen.getByText("34 ABC 11")).toBeInTheDocument();
    expect(screen.getByText("0.72")).toBeInTheDocument();
    expect(screen.getByText("Mehmet Demir")).toBeInTheDocument();
    expect(screen.getByText("22.05.2026")).toBeInTheDocument();
  });
});
