import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import { TrailerModal } from "../TrailerModal";
import { trailerModalText } from "../../../resources/tr/trailers";
import { Dorse } from "../../../types";

// framer-motion passthrough
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, onClick, ...rest }: any) => (
      <div onClick={onClick} {...rest}>
        {children}
      </div>
    ),
  },
}));

const mockOnClose = vi.fn();
const mockOnSave = vi.fn().mockResolvedValue(undefined);

const MOCK_TRAILER: Dorse = {
  id: 7,
  plaka: "06TRL007",
  marka: "Krone",
  tipi: "Frigo",
  yil: 2021,
  bos_agirlik_kg: 7000,
  maks_yuk_kapasitesi_kg: 22000,
  lastik_sayisi: 8,
  dorse_lastik_direnc_katsayisi: 0.005,
  dorse_hava_direnci: 0.18,
  aktif: true,
  notlar: "Soğutma ünitesi tamam",
};

describe("TrailerModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when isOpen=false", () => {
    const { container } = render(
      <TrailerModal
        isOpen={false}
        onClose={mockOnClose}
        onSave={mockOnSave}
        trailer={null}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders create title when no trailer provided", () => {
    render(
      <TrailerModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        trailer={null}
      />,
    );
    expect(screen.getByText(trailerModalText.title.create)).toBeInTheDocument();
  });

  it("renders edit title when trailer is provided", () => {
    render(
      <TrailerModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        trailer={MOCK_TRAILER}
      />,
    );
    expect(screen.getByText(trailerModalText.title.edit)).toBeInTheDocument();
  });

  it("pre-fills plate field when editing a trailer", () => {
    render(
      <TrailerModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        trailer={MOCK_TRAILER}
      />,
    );
    const plateInput = screen.getByPlaceholderText(
      trailerModalText.placeholders.plate,
    ) as HTMLInputElement;
    expect(plateInput.value).toBe("06TRL007");
  });

  it("calls onClose when cancel button is clicked", () => {
    render(
      <TrailerModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        trailer={null}
      />,
    );
    fireEvent.click(screen.getByText(trailerModalText.actions.cancel));
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it("shows Save button in create mode and Update in edit mode", () => {
    const { rerender } = render(
      <TrailerModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        trailer={null}
      />,
    );
    expect(screen.getByText(trailerModalText.actions.save)).toBeInTheDocument();

    rerender(
      <TrailerModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        trailer={MOCK_TRAILER}
      />,
    );
    expect(
      screen.getByText(trailerModalText.actions.update),
    ).toBeInTheDocument();
  });

  it("calls onSave when form is submitted with valid data", async () => {
    render(
      <TrailerModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        trailer={MOCK_TRAILER}
      />,
    );
    fireEvent.click(screen.getByText(trailerModalText.actions.update));
    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalledTimes(1);
    });
  });

  it("renders both basic and technical section headings", () => {
    render(
      <TrailerModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        trailer={null}
      />,
    );
    expect(
      screen.getByText(trailerModalText.sections.basic),
    ).toBeInTheDocument();
    expect(
      screen.getByText(trailerModalText.sections.technical),
    ).toBeInTheDocument();
  });
});
