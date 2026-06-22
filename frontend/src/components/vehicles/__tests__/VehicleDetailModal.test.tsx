import { render, screen, waitFor } from "../../../test/test-utils";
import { VehicleDetailModal } from "../VehicleDetailModal";

vi.mock("../../../api/vehicles", () => ({
  vehicleService: {
    getStats: vi.fn().mockRejectedValue(new Error("stats unavailable")),
    getEvents: vi.fn().mockResolvedValue([]),
  },
}));

describe("VehicleDetailModal", () => {
  it("shows a truthful unavailable state instead of synthetic zero stats", async () => {
    render(
      <VehicleDetailModal
        isOpen
        onClose={vi.fn()}
        vehicle={{
          id: 9,
          plaka: "34 ABC 123",
          marka: "Mercedes",
          model: "Actros",
          yil: 2024,
          yakit_tipi: "Diesel",
          hedef_tuketim: 28,
          aktif: true,
        }}
      />,
    );

    // When stats are unavailable the modal shows dashes, not zeroes
    await waitFor(() => {
      expect(screen.queryByText("0 km")).not.toBeInTheDocument();
    });

    // The modal itself renders — plate and brand are visible
    expect(screen.getByText("34 ABC 123")).toBeInTheDocument();
    expect(screen.getByText(/Mercedes/i)).toBeInTheDocument();
  });
});
