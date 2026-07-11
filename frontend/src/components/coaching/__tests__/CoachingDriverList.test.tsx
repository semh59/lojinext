import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/drivers", () => ({
  driverService: {
    getAll: vi.fn(),
  },
}));

import { driverService } from "../../../api/drivers";
import { CoachingDriverList } from "../CoachingDriverList";

describe("CoachingDriverList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders driver score as a converted 1-5 rating, not the raw 0.1-2.0 score value", async () => {
    // Regression: this list showed driver.score.toFixed(2) directly next
    // to a single star icon (e.g. "★ 1.00"), reading as "1/5 stars" for a
    // driver whose real 0.1-2.0 scale score is actually mid-range. Every
    // other star-rating render site in the app uses scoreToStars() for
    // this conversion — this one was missed.
    (driverService.getAll as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [
        {
          id: 1,
          ad_soyad: "Ahmet Yılmaz",
          score: 1.0, // scale midpoint — must NOT render as "1.00"/"★ 1"
          aktif: true,
        },
      ],
      total: 1,
    });

    render(<CoachingDriverList selectedDriverId={null} onSelect={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("Ahmet Yılmaz")).toBeInTheDocument();
    });

    expect(screen.getByText("2/5")).toBeInTheDocument();
    expect(screen.queryByText("1.00")).not.toBeInTheDocument();
  });
});
