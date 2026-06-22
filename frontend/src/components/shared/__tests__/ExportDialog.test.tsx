import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import { ExportDialog } from "../ExportDialog";
import { reportExportDialogText } from "../../../resources/tr/reports";

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

// vehiclesApi is only called for vehicle_report type
vi.mock("../../../services/api", () => ({
  vehiclesApi: {
    getAll: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
}));

const defaultProps = {
  isOpen: true,
  onClose: vi.fn(),
  title: "Test Raporu",
  description: "Test açıklaması",
  type: "fleet_summary" as const,
  onExport: vi.fn().mockResolvedValue(undefined),
};

describe("ExportDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultProps.onClose = vi.fn();
    defaultProps.onExport = vi.fn().mockResolvedValue(undefined);
  });

  it("renders nothing when isOpen=false", () => {
    const { container } = render(
      <ExportDialog {...defaultProps} isOpen={false} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders title and description when open", () => {
    render(<ExportDialog {...defaultProps} />);
    expect(screen.getByText("Test Raporu")).toBeInTheDocument();
    expect(screen.getByText("Test açıklaması")).toBeInTheDocument();
  });

  it("renders format label and PDF/Excel buttons", () => {
    render(<ExportDialog {...defaultProps} />);
    expect(
      screen.getByText(reportExportDialogText.fileFormat),
    ).toBeInTheDocument();
    expect(
      screen.getByText(reportExportDialogText.pdfLabel),
    ).toBeInTheDocument();
    expect(
      screen.getByText(reportExportDialogText.excelLabel),
    ).toBeInTheDocument();
  });

  it("renders date inputs and cancel button", () => {
    render(<ExportDialog {...defaultProps} />);
    expect(screen.getByText(reportExportDialogText.cancel)).toBeInTheDocument();
    // date inputs exist
    const dateInputs = document.querySelectorAll('input[type="date"]');
    expect(dateInputs.length).toBe(2);
  });

  it("calls onClose when Vazgeç is clicked", () => {
    render(<ExportDialog {...defaultProps} />);
    fireEvent.click(screen.getByText(reportExportDialogText.cancel));
    expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
  });

  it("shows PDF download button by default and calls onExport on click", async () => {
    render(<ExportDialog {...defaultProps} />);
    const downloadBtn = screen.getByText(reportExportDialogText.downloadPdf);
    expect(downloadBtn).toBeInTheDocument();
    fireEvent.click(downloadBtn);
    await waitFor(() => {
      expect(defaultProps.onExport).toHaveBeenCalledTimes(1);
    });
    expect(defaultProps.onExport).toHaveBeenCalledWith(
      expect.objectContaining({ format: "pdf" }),
    );
  });

  it("switches to Excel and shows Excel download button", async () => {
    render(<ExportDialog {...defaultProps} />);
    // Click Excel button to switch format
    fireEvent.click(screen.getByText(reportExportDialogText.excelLabel));
    await waitFor(() => {
      expect(
        screen.getByText(reportExportDialogText.downloadExcel),
      ).toBeInTheDocument();
    });
  });

  it("shows error message when onExport rejects", async () => {
    const onExportFail = vi.fn().mockRejectedValue(new Error("server error"));
    render(<ExportDialog {...defaultProps} onExport={onExportFail} />);
    fireEvent.click(screen.getByText(reportExportDialogText.downloadPdf));
    await waitFor(() => {
      expect(
        screen.getByText(reportExportDialogText.exportError),
      ).toBeInTheDocument();
    });
  });

  it("PDF button is disabled for list-type exports (pdf not supported)", () => {
    render(<ExportDialog {...defaultProps} type="trip_list" />);
    // PDF button should be disabled for trip_list
    const pdfButton = screen
      .getByText(reportExportDialogText.pdfLabel)
      .closest("button");
    expect(pdfButton).toBeDisabled();
  });
});
