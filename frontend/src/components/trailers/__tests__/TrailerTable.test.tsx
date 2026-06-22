import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "../../../test/test-utils";
import { TrailerTable } from "../TrailerTable";
import { trailerTableText } from "../../../resources/tr/trailers";
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
    tr: ({ children, className, ...rest }: any) => (
      <tr className={className} {...rest}>
        {children}
      </tr>
    ),
  },
}));

const MOCK_TRAILERS: Dorse[] = [
  {
    id: 1,
    plaka: "34TRL001",
    marka: "Krone",
    tipi: "Frigo",
    yil: 2021,
    bos_agirlik_kg: 7000,
    maks_yuk_kapasitesi_kg: 22000,
    lastik_sayisi: 8,
    aktif: true,
    notlar: null,
  },
  {
    id: 2,
    plaka: "06TRL002",
    marka: "Tırsan",
    tipi: "Standart",
    yil: 2019,
    bos_agirlik_kg: 6500,
    maks_yuk_kapasitesi_kg: 24000,
    lastik_sayisi: 6,
    aktif: false,
    notlar: null,
  },
];

describe("TrailerTable", () => {
  const mockOnEdit = vi.fn();
  const mockOnDelete = vi.fn().mockResolvedValue(undefined);
  const mockOnViewDetail = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading spinner when loading=true", () => {
    const { container } = render(
      <TrailerTable
        trailers={[]}
        loading={true}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onViewDetail={mockOnViewDetail}
      />,
    );
    // A spinning element should be present
    expect(container.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("shows empty state when no trailers", () => {
    render(
      <TrailerTable
        trailers={[]}
        loading={false}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onViewDetail={mockOnViewDetail}
      />,
    );
    expect(screen.getByText(trailerTableText.emptyTitle)).toBeInTheDocument();
    expect(
      screen.getByText(trailerTableText.emptyDescription),
    ).toBeInTheDocument();
  });

  it("renders trailer plate in grid mode (default)", () => {
    render(
      <TrailerTable
        trailers={MOCK_TRAILERS}
        loading={false}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onViewDetail={mockOnViewDetail}
      />,
    );
    expect(screen.getByText("34TRL001")).toBeInTheDocument();
    expect(screen.getByText("06TRL002")).toBeInTheDocument();
  });

  it("renders active/inactive status badges", () => {
    render(
      <TrailerTable
        trailers={MOCK_TRAILERS}
        loading={false}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onViewDetail={mockOnViewDetail}
      />,
    );
    expect(
      screen.getAllByText(trailerTableText.status.active).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText(trailerTableText.status.inactive).length,
    ).toBeGreaterThan(0);
  });

  it("renders title and total count", () => {
    render(
      <TrailerTable
        trailers={MOCK_TRAILERS}
        loading={false}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onViewDetail={mockOnViewDetail}
      />,
    );
    expect(screen.getByText(trailerTableText.title)).toBeInTheDocument();
    expect(
      screen.getByText(trailerTableText.totalCount(2)),
    ).toBeInTheDocument();
  });

  it("renders list view with column headers", () => {
    render(
      <TrailerTable
        trailers={MOCK_TRAILERS}
        loading={false}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onViewDetail={mockOnViewDetail}
        viewMode="list"
      />,
    );
    expect(
      screen.getByText(trailerTableText.columns.plateAndBrand),
    ).toBeInTheDocument();
    expect(
      screen.getByText(trailerTableText.columns.status),
    ).toBeInTheDocument();
  });

  it("calls onViewDetail when details button clicked in grid mode", () => {
    render(
      <TrailerTable
        trailers={[MOCK_TRAILERS[0]]}
        loading={false}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onViewDetail={mockOnViewDetail}
      />,
    );
    // Grid mode uses "Detaylar"
    fireEvent.click(screen.getByText(trailerTableText.actions.details));
    expect(mockOnViewDetail).toHaveBeenCalledTimes(1);
    expect(mockOnViewDetail).toHaveBeenCalledWith(MOCK_TRAILERS[0]);
  });
});
