import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/executive", () => ({
  executiveService: { downloadPdf: vi.fn() },
}));

const notifyMock = vi.fn();
vi.mock("../../../context/NotificationContext", async () => {
  const actual: any = await vi.importActual(
    "../../../context/NotificationContext",
  );
  return { ...actual, useNotify: () => ({ notify: notifyMock }) };
});

import { executiveService } from "../../../api/executive";
import { DownloadPdfButton } from "../DownloadPdfButton";

describe("DownloadPdfButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    notifyMock.mockClear();
  });

  it("happy path → downloadPdf çağrılır ve başarı toast'ı gösterilir", async () => {
    (
      executiveService.downloadPdf as ReturnType<typeof vi.fn>
    ).mockResolvedValue(undefined);
    render(<DownloadPdfButton />);
    fireEvent.click(screen.getByRole("button", { name: /CEO 1-pager/i }));
    await waitFor(() =>
      expect(executiveService.downloadPdf).toHaveBeenCalled(),
    );
    // Regression: a successful download previously gave no feedback at
    // all (no toast, no visible state change) — a user had no way to
    // know the download started or finished.
    expect(notifyMock).toHaveBeenCalledWith("success", expect.any(String));
  });

  it('404 → "henüz hazır değil" uyarı toast', async () => {
    (
      executiveService.downloadPdf as ReturnType<typeof vi.fn>
    ).mockRejectedValue({ response: { status: 404 } });
    render(<DownloadPdfButton />);
    fireEvent.click(screen.getByRole("button", { name: /CEO 1-pager/i }));
    await waitFor(() =>
      expect(notifyMock).toHaveBeenCalledWith(
        "warning",
        expect.stringContaining("hazır değil"),
      ),
    );
  });
});
