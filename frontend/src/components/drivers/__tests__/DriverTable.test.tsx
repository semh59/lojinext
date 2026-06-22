import { render, screen, fireEvent } from "../../../test/test-utils";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { DriverTable } from "../DriverTable";
import { driverTableText } from "../../../resources/tr/drivers";
import type { Driver } from "../../../types";

// framer-motion passthrough
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, className, style, ...rest }: any) => (
      <div className={className} style={style} {...rest}>
        {children}
      </div>
    ),
  },
}));

const MOCK_DRIVERS: Driver[] = [
  {
    id: 1,
    ad_soyad: "Ahmet Yılmaz",
    telefon: "0532 111 22 33",
    ehliyet_sinifi: "CE",
    score: 4,
    aktif: true,
  },
  {
    id: 2,
    ad_soyad: "Mehmet Kara",
    telefon: null,
    ehliyet_sinifi: "C",
    score: 2,
    aktif: false,
  },
];

const mockOnEdit = vi.fn();
const mockOnDelete = vi.fn();
const mockOnScoreClick = vi.fn();
const mockOnPerformanceClick = vi.fn();

describe("DriverTable", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders table column headers", () => {
    render(
      <DriverTable
        drivers={[]}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onScoreClick={mockOnScoreClick}
        onPerformanceClick={mockOnPerformanceClick}
      />,
    );
    expect(
      screen.getByText(driverTableText.columns.driver),
    ).toBeInTheDocument();
    expect(
      screen.getByText(driverTableText.columns.contact),
    ).toBeInTheDocument();
    expect(screen.getByText(driverTableText.columns.score)).toBeInTheDocument();
    expect(
      screen.getByText(driverTableText.columns.status),
    ).toBeInTheDocument();
    expect(
      screen.getByText(driverTableText.columns.actions),
    ).toBeInTheDocument();
  });

  it("renders driver names", () => {
    render(
      <DriverTable
        drivers={MOCK_DRIVERS}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onScoreClick={mockOnScoreClick}
        onPerformanceClick={mockOnPerformanceClick}
      />,
    );
    expect(screen.getByText("Ahmet Yılmaz")).toBeInTheDocument();
    expect(screen.getByText("Mehmet Kara")).toBeInTheDocument();
  });

  it("renders license class suffix for each driver", () => {
    render(
      <DriverTable
        drivers={MOCK_DRIVERS}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onScoreClick={mockOnScoreClick}
        onPerformanceClick={mockOnPerformanceClick}
      />,
    );
    expect(
      screen.getByText(driverTableText.licenseSuffix("CE")),
    ).toBeInTheDocument();
    expect(
      screen.getByText(driverTableText.licenseSuffix("C")),
    ).toBeInTheDocument();
  });

  it("shows active/inactive status badges", () => {
    render(
      <DriverTable
        drivers={MOCK_DRIVERS}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onScoreClick={mockOnScoreClick}
        onPerformanceClick={mockOnPerformanceClick}
      />,
    );
    expect(screen.getByText(driverTableText.status.active)).toBeInTheDocument();
    expect(
      screen.getByText(driverTableText.status.inactive),
    ).toBeInTheDocument();
  });

  it("shows phone number or dash for missing phone", () => {
    render(
      <DriverTable
        drivers={MOCK_DRIVERS}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onScoreClick={mockOnScoreClick}
        onPerformanceClick={mockOnPerformanceClick}
      />,
    );
    expect(screen.getByText("0532 111 22 33")).toBeInTheDocument();
    expect(screen.getByText("-")).toBeInTheDocument();
  });

  it("calls onEdit when edit button is clicked", () => {
    render(
      <DriverTable
        drivers={MOCK_DRIVERS}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onScoreClick={mockOnScoreClick}
        onPerformanceClick={mockOnPerformanceClick}
      />,
    );
    const editButtons = screen.getAllByTitle(driverTableText.actions.edit);
    fireEvent.click(editButtons[0]);
    expect(mockOnEdit).toHaveBeenCalledWith(MOCK_DRIVERS[0]);
  });

  it("calls onDelete when delete button is clicked", () => {
    render(
      <DriverTable
        drivers={MOCK_DRIVERS}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onScoreClick={mockOnScoreClick}
        onPerformanceClick={mockOnPerformanceClick}
      />,
    );
    const deleteButtons = screen.getAllByTitle(driverTableText.actions.delete);
    fireEvent.click(deleteButtons[1]);
    expect(mockOnDelete).toHaveBeenCalledWith(MOCK_DRIVERS[1]);
  });

  it("calls onScoreClick when score button is clicked", () => {
    render(
      <DriverTable
        drivers={MOCK_DRIVERS}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onScoreClick={mockOnScoreClick}
        onPerformanceClick={mockOnPerformanceClick}
      />,
    );
    const scoreButtons = screen.getAllByTitle(driverTableText.actions.score);
    fireEvent.click(scoreButtons[0]);
    expect(mockOnScoreClick).toHaveBeenCalledWith(MOCK_DRIVERS[0]);
  });

  it("calls onPerformanceClick when AI analysis button is clicked", () => {
    render(
      <DriverTable
        drivers={MOCK_DRIVERS}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onScoreClick={mockOnScoreClick}
        onPerformanceClick={mockOnPerformanceClick}
      />,
    );
    const aiButtons = screen.getAllByTitle(driverTableText.actions.aiAnalysis);
    fireEvent.click(aiButtons[0]);
    expect(mockOnPerformanceClick).toHaveBeenCalledWith(MOCK_DRIVERS[0]);
  });

  it("renders selection checkbox column when onToggleSelection is provided", () => {
    const mockToggle = vi.fn();
    render(
      <DriverTable
        drivers={MOCK_DRIVERS}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onScoreClick={mockOnScoreClick}
        onPerformanceClick={mockOnPerformanceClick}
        selectedIds={[]}
        onToggleSelection={mockToggle}
        onToggleAll={vi.fn()}
      />,
    );
    // Header "select all" checkbox + one per driver
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes.length).toBe(3); // 1 header + 2 rows
  });

  it("marks 'select all' checkbox as checked when all drivers are selected", () => {
    const mockToggle = vi.fn();
    render(
      <DriverTable
        drivers={MOCK_DRIVERS}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onScoreClick={mockOnScoreClick}
        onPerformanceClick={mockOnPerformanceClick}
        selectedIds={[1, 2]}
        onToggleSelection={mockToggle}
        onToggleAll={vi.fn()}
      />,
    );
    const headerCheckbox = screen.getByLabelText("Tümünü seç");
    expect(headerCheckbox).toBeChecked();
  });

  it("renders first letter of driver name as avatar", () => {
    render(
      <DriverTable
        drivers={[MOCK_DRIVERS[0]]}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onScoreClick={mockOnScoreClick}
        onPerformanceClick={mockOnPerformanceClick}
      />,
    );
    // "Ahmet Yılmaz"[0] = "A"
    expect(screen.getByText("A")).toBeInTheDocument();
  });
});
