import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "../../../test/test-utils";
import { BreakdownReportModal } from "../BreakdownReportModal";

vi.mock("@/api/vehicles", () => ({
  vehicleService: {
    getAll: vi.fn().mockResolvedValue({
      items: [{ id: 1, plaka: "34 A 1", marka: "MAN" }],
      total: 1,
    }),
  },
}));

vi.mock("@/services/dorseService", () => ({
  dorseService: {
    getAll: vi
      .fn()
      .mockResolvedValue([{ id: 5, plaka: "34 D 5", tipi: "Tenteli" }]),
  },
}));

vi.mock("@/context/NotificationContext", () => ({
  useNotify: () => ({ notify: vi.fn() }),
}));

vi.mock("@/services/api/axios-instance", () => ({
  default: { post: vi.fn().mockResolvedValue({ data: {} }) },
}));

describe("BreakdownReportModal", () => {
  it("renders the breakdown form with target toggle", () => {
    render(<BreakdownReportModal isOpen onClose={vi.fn()} />);
    expect(screen.getByText("Arıza Bildir")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Araç" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dorse" })).toBeInTheDocument();
  });

  it("switches to the dorse dropdown", async () => {
    render(<BreakdownReportModal isOpen onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Dorse" }));
    expect(await screen.findByText("Dorse seçiniz…")).toBeInTheDocument();
  });

  it("requires a target before submitting", () => {
    render(<BreakdownReportModal isOpen onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Bildir" }));
    expect(screen.getByText("Araç seçiniz.")).toBeInTheDocument();
  });
});
