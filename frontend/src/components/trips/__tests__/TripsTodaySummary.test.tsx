import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/trips", () => ({
  tripService: {
    getStats: vi.fn(),
  },
}));

import { tripService } from "../../../api/trips";
import { TripsTodaySummary } from "../TripsTodaySummary";

describe("TripsTodaySummary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("sefer toplamı ve durum çiplerini gösterir", async () => {
    (tripService.getStats as ReturnType<typeof vi.fn>).mockResolvedValue({
      total_count: 12,
      completed_count: 4,
      cancelled_count: 0,
      planned_count: 5,
      in_progress_count: 3,
      total_distance_km: 0,
      avg_consumption: 0,
    });
    render(<TripsTodaySummary />);
    await waitFor(() => expect(screen.getByText("12")).toBeInTheDocument());
    expect(screen.getByText(/Yolda:/)).toBeInTheDocument();
    expect(screen.getByText(/Tamamlandı:/)).toBeInTheDocument();
    // İptal=0 ise chip görünmemeli
    expect(screen.queryByText(/İptal:/)).not.toBeInTheDocument();
  });

  it("total=0 → boş gün mesajı", async () => {
    (tripService.getStats as ReturnType<typeof vi.fn>).mockResolvedValue({
      total_count: 0,
      completed_count: 0,
      cancelled_count: 0,
      planned_count: 0,
      in_progress_count: 0,
      total_distance_km: 0,
      avg_consumption: 0,
    });
    render(<TripsTodaySummary />);
    await waitFor(() =>
      expect(
        screen.getByText("Bugün için kayıtlı sefer yok."),
      ).toBeInTheDocument(),
    );
  });

  it("iptal sayısı > 0 ise İptal chip görünür", async () => {
    (tripService.getStats as ReturnType<typeof vi.fn>).mockResolvedValue({
      total_count: 8,
      completed_count: 3,
      cancelled_count: 2,
      planned_count: 1,
      in_progress_count: 2,
      total_distance_km: 0,
      avg_consumption: 0,
    });
    render(<TripsTodaySummary />);
    await waitFor(() => expect(screen.getByText(/İptal:/)).toBeInTheDocument());
  });
});
