import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import { DriverModal } from "../DriverModal";
import { driverModalText } from "../../../resources/tr/drivers";
import { Driver } from "../../../types";

// Mock framer-motion to avoid animation issues
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
}));

const mockOnClose = vi.fn();
const mockOnSave = vi.fn().mockResolvedValue(undefined);

const MOCK_DRIVER: Driver = {
  id: 1,
  ad_soyad: "Mehmet Demir",
  telefon: "05321234567",
  ise_baslama: "2023-01-15T00:00:00",
  ehliyet_sinifi: "E",
  manual_score: 1.5,
  score: 1.5,
  notlar: "Deneyimli sürücü",
  aktif: true,
  tc_no: "12345678901",
  dogum_tarihi: "1985-03-20T00:00:00",
  kan_grubu: "A+",
  telegram_id: "123456789",
};

describe("DriverModal — create mode", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders null when isOpen=false", () => {
    const { container } = render(
      <DriverModal
        isOpen={false}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={null}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders create title when no driver provided", () => {
    render(
      <DriverModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={null}
      />,
    );
    expect(screen.getByText(driverModalText.title.create)).toBeInTheDocument();
  });

  it("renders tab navigation", () => {
    render(
      <DriverModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={null}
      />,
    );
    expect(screen.getByText("Temel Bilgiler")).toBeInTheDocument();
    expect(screen.getByText("Kişisel")).toBeInTheDocument();
    expect(screen.getByText("Telegram")).toBeInTheDocument();
  });

  it("renders form fields on temel tab", () => {
    render(
      <DriverModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={null}
      />,
    );
    expect(
      screen.getByPlaceholderText(driverModalText.placeholders.fullName),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(driverModalText.placeholders.phone),
    ).toBeInTheDocument();
  });

  it("calls onClose when close (X) button clicked", () => {
    render(
      <DriverModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={null}
      />,
    );
    const cancelBtn = screen.getByText(driverModalText.actions.cancel);
    fireEvent.click(cancelBtn);
    expect(mockOnClose).toHaveBeenCalled();
  });

  it("shows validation error for short name", async () => {
    render(
      <DriverModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={null}
      />,
    );
    const nameInput = screen.getByPlaceholderText(
      driverModalText.placeholders.fullName,
    );
    fireEvent.change(nameInput, { target: { value: "A" } });
    fireEvent.click(screen.getByText(driverModalText.actions.save));
    await waitFor(() => {
      expect(
        screen.getByText(driverModalText.validation.nameMin),
      ).toBeInTheDocument();
    });
  });

  it("submits form and calls onSave with valid data", async () => {
    render(
      <DriverModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={null}
      />,
    );
    const nameInput = screen.getByPlaceholderText(
      driverModalText.placeholders.fullName,
    );
    fireEvent.change(nameInput, { target: { value: "Ali Veli Örnek" } });
    fireEvent.click(screen.getByText(driverModalText.actions.save));
    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalledWith(
        expect.objectContaining({ ad_soyad: "Ali Veli Örnek" }),
      );
    });
  });
});

describe("DriverModal — edit mode", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders edit title when driver provided", () => {
    render(
      <DriverModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={MOCK_DRIVER}
      />,
    );
    expect(screen.getByText(driverModalText.title.edit)).toBeInTheDocument();
  });

  it("pre-fills form with driver data", () => {
    render(
      <DriverModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={MOCK_DRIVER}
      />,
    );
    const nameInput = screen.getByDisplayValue("Mehmet Demir");
    expect(nameInput).toBeInTheDocument();
  });

  it("switches to Kişisel tab", () => {
    render(
      <DriverModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={MOCK_DRIVER}
      />,
    );
    const kisiselTab = screen.getByText("Kişisel");
    fireEvent.click(kisiselTab);
    expect(
      screen.getByPlaceholderText("11 haneli TC kimlik numarası"),
    ).toBeInTheDocument();
  });

  it("switches to Telegram tab and shows helper text", () => {
    render(
      <DriverModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={MOCK_DRIVER}
      />,
    );
    const telegramTab = screen.getByText("Telegram");
    fireEvent.click(telegramTab);
    expect(
      screen.getByText("Telegram botu nasıl kullanılır?"),
    ).toBeInTheDocument();
  });

  it("shows Güncelle button in edit mode", () => {
    render(
      <DriverModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={MOCK_DRIVER}
      />,
    );
    expect(
      screen.getByText(driverModalText.actions.update),
    ).toBeInTheDocument();
  });
});
