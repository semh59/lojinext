import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/executive", () => ({
  executiveService: {
    getFvi: vi.fn(),
  },
}));

import { executiveService } from "../../../api/executive";
import { FleetEfficiencyCard } from "../FleetEfficiencyCard";

describe("FleetEfficiencyCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("happy path → FVI + alt skorlar render edilir", async () => {
    (executiveService.getFvi as ReturnType<typeof vi.fn>).mockResolvedValue({
      fvi: 78,
      fuel_score: 82,
      maintenance_score: 75,
      driver_score: 80,
      anomaly_quality_score: 73,
      confidence: 1.0,
      trend_30d: 4,
      reasons: [],
      computed_at: new Date().toISOString(),
    });
    render(<FleetEfficiencyCard />);
    await waitFor(() => screen.getByText("78"));
    // Trend pozitif olduğu için +4 görünür
    expect(screen.getByText("+4.0")).toBeInTheDocument();
    // Alt skor başlıkları
    expect(screen.getByText("Yakıt")).toBeInTheDocument();
    expect(screen.getByText("Bakım")).toBeInTheDocument();
    expect(screen.getByText("Şoför")).toBeInTheDocument();
  });

  it('low confidence → "cold-start" uyarısı görünür', async () => {
    (executiveService.getFvi as ReturnType<typeof vi.fn>).mockResolvedValue({
      fvi: 75,
      fuel_score: 75,
      maintenance_score: 75,
      driver_score: 75,
      anomaly_quality_score: 75,
      confidence: 0.25,
      trend_30d: null,
      reasons: [],
      computed_at: new Date().toISOString(),
    });
    render(<FleetEfficiencyCard />);
    await waitFor(() =>
      expect(screen.getByText(/cold-start/i)).toBeInTheDocument(),
    );
  });

  it('503 hata → "modülü devre dışı" mesajı', async () => {
    (executiveService.getFvi as ReturnType<typeof vi.fn>).mockRejectedValue({
      response: { status: 503 },
    });
    render(<FleetEfficiencyCard />);
    await waitFor(() =>
      expect(screen.getByText(/modülü devre dışı/i)).toBeInTheDocument(),
    );
  });
});
