import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/vehicles", () => ({
  vehicleService: {
    getInspectionAlerts: vi.fn(),
  },
}));

import { vehicleService } from "../../../api/vehicles";
import { InspectionAlertModal } from "../InspectionAlertModal";

describe("InspectionAlertModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("isOpen=false ise hiçbir şey render edilmez", () => {
    const { container } = render(
      <InspectionAlertModal isOpen={false} onClose={() => {}} />,
    );
    expect(container.firstChild).toBeNull();
    expect(vehicleService.getInspectionAlerts).not.toHaveBeenCalled();
  });

  it('boş listeyle "filo temiz" mesajı', async () => {
    (
      vehicleService.getInspectionAlerts as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      expiring: [],
      overdue: [],
      within_days: 30,
    });
    render(<InspectionAlertModal isOpen onClose={() => {}} />);
    await waitFor(() =>
      expect(
        screen.getByText(/Yaklaşan veya geçmiş muayene yok/),
      ).toBeInTheDocument(),
    );
  });

  it("overdue + expiring araçlar ayrı sectionlarda gösterilir", async () => {
    (
      vehicleService.getInspectionAlerts as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      expiring: [
        {
          id: 1,
          plaka: "34 ABC 123",
          marka: "Volvo",
          model: "FH16",
          yil: 2022,
          muayene_tarihi: "2026-06-10",
          days_remaining: 14,
        },
      ],
      overdue: [
        {
          id: 2,
          plaka: "34 XYZ 999",
          marka: "Mercedes",
          model: "Actros",
          yil: 2018,
          muayene_tarihi: "2026-04-15",
          days_remaining: -37,
        },
      ],
      within_days: 30,
    });
    render(<InspectionAlertModal isOpen onClose={() => {}} />);
    await waitFor(() =>
      expect(screen.getByText("34 ABC 123")).toBeInTheDocument(),
    );
    expect(screen.getByText("34 XYZ 999")).toBeInTheDocument();
    expect(screen.getByText(/14 gün kaldı/)).toBeInTheDocument();
    expect(screen.getByText(/gün geçmiş/)).toBeInTheDocument();
    // formatDate DD.MM.YYYY
    expect(screen.getByText(/10\.06\.2026/)).toBeInTheDocument();
  });
});
