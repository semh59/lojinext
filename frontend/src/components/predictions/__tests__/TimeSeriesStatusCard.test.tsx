import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/predictions", () => ({
  predictionService: {
    timeSeriesStatus: vi.fn(),
  },
}));

import { predictionService } from "../../../api/predictions";
import { TimeSeriesStatusCard } from "../TimeSeriesStatusCard";

describe("TimeSeriesStatusCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("available=true → Hazır + yöntem gösterir", async () => {
    (
      predictionService.timeSeriesStatus as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      available: true,
      method: "ARIMA",
      history_days: 90,
    });
    render(<TimeSeriesStatusCard />);
    await waitFor(() => expect(screen.getByText("Hazır")).toBeInTheDocument());
    expect(screen.getByText(/ARIMA/)).toBeInTheDocument();
    expect(screen.getByText(/90 günlük geçmiş/)).toBeInTheDocument();
  });

  it("available=false → Yeterli veri yok uyarısı", async () => {
    (
      predictionService.timeSeriesStatus as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      available: false,
    });
    render(<TimeSeriesStatusCard />);
    await waitFor(() =>
      expect(screen.getByText("Yeterli veri yok")).toBeInTheDocument(),
    );
  });
});
