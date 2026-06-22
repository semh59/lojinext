import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import { DriverScoreModal } from "../DriverScoreModal";
import { driverScoreText } from "../../../resources/tr/drivers";
import { Driver } from "../../../types";

// framer-motion passthrough
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
  },
}));

const mockOnClose = vi.fn();
const mockOnSave = vi.fn().mockResolvedValue(undefined);

const MOCK_DRIVER: Driver = {
  id: 3,
  ad_soyad: "Ahmet Yılmaz",
  ehliyet_sinifi: "CE",
  score: 1.4,
  manual_score: 1.2,
  aktif: true,
};

describe("DriverScoreModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when isOpen=false", () => {
    const { container } = render(
      <DriverScoreModal
        isOpen={false}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={MOCK_DRIVER}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when driver=null even if open", () => {
    const { container } = render(
      <DriverScoreModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={null}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders modal title and driver name when open", () => {
    render(
      <DriverScoreModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={MOCK_DRIVER}
      />,
    );
    expect(screen.getByText(driverScoreText.title)).toBeInTheDocument();
    expect(screen.getByText("Ahmet Yılmaz")).toBeInTheDocument();
  });

  it("shows the current driver score", () => {
    render(
      <DriverScoreModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={MOCK_DRIVER}
      />,
    );
    // Current score and estimated hybrid can both render "1.40" — use getAllByText
    expect(screen.getAllByText("1.40").length).toBeGreaterThan(0);
  });

  it("shows score band labels", () => {
    render(
      <DriverScoreModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={MOCK_DRIVER}
      />,
    );
    expect(
      screen.getByText(driverScoreText.scoreBands.risk),
    ).toBeInTheDocument();
    expect(
      screen.getByText(driverScoreText.scoreBands.neutral),
    ).toBeInTheDocument();
    expect(
      screen.getByText(driverScoreText.scoreBands.excellent),
    ).toBeInTheDocument();
  });

  it("calls onClose when cancel button is clicked", () => {
    render(
      <DriverScoreModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={MOCK_DRIVER}
      />,
    );
    fireEvent.click(screen.getByText(driverScoreText.actions.cancel));
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it("calls onSave when update button is submitted", async () => {
    render(
      <DriverScoreModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={MOCK_DRIVER}
      />,
    );
    fireEvent.click(screen.getByText(driverScoreText.actions.update));
    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalledTimes(1);
    });
  });

  it("shows the hybrid formula hint", () => {
    render(
      <DriverScoreModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        driver={MOCK_DRIVER}
      />,
    );
    expect(
      screen.getByText(driverScoreText.labels.hybridFormula),
    ).toBeInTheDocument();
  });
});
