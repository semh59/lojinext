import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/locations", () => ({
  locationService: {
    calibrateFromTrip: vi.fn(),
  },
}));

import { locationService } from "../../../api/locations";
import { CalibrationModal } from "../CalibrationModal";

describe("CalibrationModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("isOpen=false ise hiçbir şey render edilmez", () => {
    const { container } = render(
      <CalibrationModal isOpen={false} onClose={() => {}} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("routeLabel başlık altında gösterilir", () => {
    render(
      <CalibrationModal
        isOpen
        onClose={() => {}}
        routeLabel="Istanbul → Ankara"
      />,
    );
    expect(screen.getByText("Istanbul → Ankara")).toBeInTheDocument();
  });

  it("Sefer ID boş veya negatif iken Kalibre Et disabled", () => {
    render(<CalibrationModal isOpen onClose={() => {}} />);
    const button = screen.getByRole("button", { name: /Kalibre Et/ });
    expect(button).toBeDisabled();
  });

  it("geçerli ID ile başarılı kalibrasyon yeşil mesaj gösterir", async () => {
    (
      locationService.calibrateFromTrip as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      success: true,
      message: "Güzergah kalibrasyonu tamamlandı.",
    });

    render(<CalibrationModal isOpen onClose={() => {}} />);
    const input = screen.getByLabelText("Sefer ID") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "42" } });
    fireEvent.click(screen.getByRole("button", { name: /Kalibre Et/ }));

    await waitFor(() =>
      expect(
        screen.getByText("Güzergah kalibrasyonu tamamlandı."),
      ).toBeInTheDocument(),
    );
    expect(locationService.calibrateFromTrip).toHaveBeenCalledWith(42);
  });

  it("backend 400 detail mesajını kırmızı banner olarak gösterir", async () => {
    const err: any = new Error("boom");
    err.response = { status: 400, data: { detail: "Veri eksik" } };
    (
      locationService.calibrateFromTrip as ReturnType<typeof vi.fn>
    ).mockRejectedValue(err);

    render(<CalibrationModal isOpen onClose={() => {}} />);
    fireEvent.change(screen.getByLabelText("Sefer ID"), {
      target: { value: "1" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Kalibre Et/ }));

    await waitFor(() =>
      expect(screen.getByText("Veri eksik")).toBeInTheDocument(),
    );
  });
});
