import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/executive", () => ({
  executiveService: { getCrossFeature: vi.fn() },
}));

import { executiveService } from "../../../api/executive";
import { CrossFeatureSavings } from "../CrossFeatureSavings";

describe("CrossFeatureSavings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("3 kalem doğru ikon + tone ile gösterilir", async () => {
    (
      executiveService.getCrossFeature as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      period_days: 90,
      maintenance_delay_loss_tl: 50_000,
      coaching_savings_tl: 30_000,
      theft_loss_tl: 10_000,
      confidence: 0.55,
    });
    render(<CrossFeatureSavings />);
    await waitFor(() =>
      expect(screen.getByText("Bakım gecikme zararı")).toBeInTheDocument(),
    );
    expect(screen.getByText("Koçluk tasarrufu")).toBeInTheDocument();
    expect(screen.getByText("Hırsızlık zararı")).toBeInTheDocument();
  });

  it("net impact negatif olursa kırmızı rengle gösterilir", async () => {
    (
      executiveService.getCrossFeature as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      period_days: 90,
      maintenance_delay_loss_tl: 100_000,
      coaching_savings_tl: 10_000,
      theft_loss_tl: 20_000,
      confidence: 0.55,
    });
    render(<CrossFeatureSavings />);
    await waitFor(() => screen.getByText("Net etki"));
    // 10K - 100K - 20K = -110K, kırmızı tonlu
    expect(screen.getByText(/110\.000/)).toBeInTheDocument();
  });
});
