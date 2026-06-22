import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "../../../test/test-utils";
import TrailerDetailModal from "../TrailerDetailModal";
import { trailerDetailText } from "../../../resources/tr/trailers";
import { Dorse } from "../../../types";

// framer-motion passthrough
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, onClick, className, ...rest }: any) => (
      <div onClick={onClick} className={className} {...rest}>
        {children}
      </div>
    ),
  },
}));

const MOCK_TRAILER: Dorse = {
  id: 5,
  plaka: "34TRL999",
  marka: "Krone",
  model: "Mega",
  tipi: "Frigo",
  yil: 2020,
  bos_agirlik_kg: 7500,
  maks_yuk_kapasitesi_kg: 22000,
  lastik_sayisi: 8,
  aktif: true,
  notlar: "Test notu",
};

describe("TrailerDetailModal", () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when trailer is null", () => {
    const { container } = render(
      <TrailerDetailModal trailer={null} onClose={mockOnClose} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows trailer plate and brand/model in header", () => {
    render(<TrailerDetailModal trailer={MOCK_TRAILER} onClose={mockOnClose} />);
    // plate appears in header h2 and in InfoCard — use getAllByText
    expect(screen.getAllByText("34TRL999").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Krone.*Mega/).length).toBeGreaterThan(0);
  });

  it("shows active status badge for active trailer", () => {
    render(<TrailerDetailModal trailer={MOCK_TRAILER} onClose={mockOnClose} />);
    expect(
      screen.getByText(trailerDetailText.status.active),
    ).toBeInTheDocument();
  });

  it("shows inactive status badge for inactive trailer", () => {
    const inactiveTrailer = { ...MOCK_TRAILER, aktif: false };
    render(
      <TrailerDetailModal trailer={inactiveTrailer} onClose={mockOnClose} />,
    );
    expect(
      screen.getByText(trailerDetailText.status.inactive),
    ).toBeInTheDocument();
  });

  it("renders three tabs: General, Technical, Maintenance", () => {
    render(<TrailerDetailModal trailer={MOCK_TRAILER} onClose={mockOnClose} />);
    expect(
      screen.getByText(trailerDetailText.tabs.general),
    ).toBeInTheDocument();
    expect(
      screen.getByText(trailerDetailText.tabs.technical),
    ).toBeInTheDocument();
    expect(
      screen.getByText(trailerDetailText.tabs.maintenance),
    ).toBeInTheDocument();
  });

  it("shows plate field label and value on General tab by default", () => {
    render(<TrailerDetailModal trailer={MOCK_TRAILER} onClose={mockOnClose} />);
    expect(
      screen.getByText(trailerDetailText.fields.plate),
    ).toBeInTheDocument();
    // plate value appears multiple times (header + info card)
    expect(screen.getAllByText("34TRL999").length).toBeGreaterThan(0);
  });

  it("switches to Technical tab and shows weight section", () => {
    render(<TrailerDetailModal trailer={MOCK_TRAILER} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText(trailerDetailText.tabs.technical));
    expect(
      screen.getByText(trailerDetailText.sections.weight),
    ).toBeInTheDocument();
    expect(
      screen.getByText(trailerDetailText.fields.emptyWeight),
    ).toBeInTheDocument();
  });

  it("shows maintenance unavailable message on Maintenance tab", () => {
    render(<TrailerDetailModal trailer={MOCK_TRAILER} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText(trailerDetailText.tabs.maintenance));
    expect(
      screen.getByText(trailerDetailText.maintenance.unavailableTitle),
    ).toBeInTheDocument();
  });

  it("calls onClose when Kapat button is clicked", () => {
    render(<TrailerDetailModal trailer={MOCK_TRAILER} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText(trailerDetailText.fields.close));
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it("shows dash fallback for null notes", () => {
    const noNotesTrailer = { ...MOCK_TRAILER, notlar: null };
    render(
      <TrailerDetailModal trailer={noNotesTrailer} onClose={mockOnClose} />,
    );
    // notes field shows "-" when null
    expect(
      screen.getByText(trailerDetailText.fields.notes),
    ).toBeInTheDocument();
  });
});
