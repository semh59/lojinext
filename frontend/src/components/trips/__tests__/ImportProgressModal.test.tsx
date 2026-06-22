import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import { ImportProgressModal } from "../ImportProgressModal";

// Mock trip-service
vi.mock("../../../api/trips", () => ({
  tripService: {
    uploadExcelAsync: vi.fn(),
    getTaskStatus: vi.fn(),
  },
}));

// Mock useTaskStatus hook
vi.mock("../../../hooks/useTaskStatus", () => ({
  useTaskStatus: vi.fn(),
}));

const DEFAULT_TASK = {
  status: "IDLE",
  result: null,
  error: null,
  isTerminal: false,
};

function makeFile(name = "trips.xlsx") {
  return new File(["dummy content"], name, {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
}

describe("ImportProgressModal", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const { useTaskStatus } = await import("../../../hooks/useTaskStatus");
    (useTaskStatus as ReturnType<typeof vi.fn>).mockReturnValue(DEFAULT_TASK);
    const { tripService } = await import("../../../api/trips");
    (
      tripService.uploadExcelAsync as ReturnType<typeof vi.fn>
    ).mockResolvedValue({ task_id: "task-abc-123" });
  });

  it("renders nothing when file is null", () => {
    const { container } = render(
      <ImportProgressModal file={null} onClose={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders modal when file is provided", () => {
    render(<ImportProgressModal file={makeFile()} onClose={vi.fn()} />);
    expect(screen.getByText("Excel İçe Aktarma")).toBeInTheDocument();
  });

  it("shows the file name in the header", () => {
    render(
      <ImportProgressModal
        file={makeFile("sefer_data.xlsx")}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByText("sefer_data.xlsx")).toBeInTheDocument();
  });

  it("shows processing state when task status is PROCESSING", async () => {
    const { useTaskStatus } = await import("../../../hooks/useTaskStatus");
    (useTaskStatus as ReturnType<typeof vi.fn>).mockReturnValue({
      status: "PROCESSING",
      result: null,
      error: null,
      isTerminal: false,
    });
    render(<ImportProgressModal file={makeFile()} onClose={vi.fn()} />);
    expect(screen.getByText("İşleniyor…")).toBeInTheDocument();
  });

  it("shows processing description text", async () => {
    const { useTaskStatus } = await import("../../../hooks/useTaskStatus");
    (useTaskStatus as ReturnType<typeof vi.fn>).mockReturnValue({
      status: "PROCESSING",
      result: null,
      error: null,
      isTerminal: false,
    });
    render(<ImportProgressModal file={makeFile()} onClose={vi.fn()} />);
    expect(
      screen.getByText(
        "Excel satırları analiz ediliyor. Büyük dosyalar birkaç dakika sürebilir.",
      ),
    ).toBeInTheDocument();
  });

  it("close button is disabled while PROCESSING", async () => {
    const { useTaskStatus } = await import("../../../hooks/useTaskStatus");
    (useTaskStatus as ReturnType<typeof vi.fn>).mockReturnValue({
      status: "PROCESSING",
      result: null,
      error: null,
      isTerminal: false,
    });
    render(<ImportProgressModal file={makeFile()} onClose={vi.fn()} />);
    const closeBtn = screen.getByLabelText("Kapat");
    expect((closeBtn as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows error message on FAILED status", async () => {
    const { useTaskStatus } = await import("../../../hooks/useTaskStatus");
    (useTaskStatus as ReturnType<typeof vi.fn>).mockReturnValue({
      status: "FAILED",
      result: null,
      error: "Dosya formatı geçersiz.",
      isTerminal: true,
    });
    render(<ImportProgressModal file={makeFile()} onClose={vi.fn()} />);
    expect(screen.getByText("Dosya formatı geçersiz.")).toBeInTheDocument();
  });

  it("shows default failed message when error is null", async () => {
    const { useTaskStatus } = await import("../../../hooks/useTaskStatus");
    (useTaskStatus as ReturnType<typeof vi.fn>).mockReturnValue({
      status: "FAILED",
      result: null,
      error: null,
      isTerminal: true,
    });
    render(<ImportProgressModal file={makeFile()} onClose={vi.fn()} />);
    expect(screen.getByText("İçe aktarma başarısız oldu.")).toBeInTheDocument();
  });

  it("shows SUCCESS summary with Tamamlandı message", async () => {
    const { useTaskStatus } = await import("../../../hooks/useTaskStatus");
    (useTaskStatus as ReturnType<typeof vi.fn>).mockReturnValue({
      status: "SUCCESS",
      result: {
        success: true,
        total_rows: 10,
        success_count: 10,
        failed_count: 0,
        errors: [],
      },
      error: null,
      isTerminal: true,
    });
    render(<ImportProgressModal file={makeFile()} onClose={vi.fn()} />);
    expect(
      screen.getByText("Tamamlandı: 10 satır işlendi."),
    ).toBeInTheDocument();
  });

  it("shows stat cards with correct labels in SUCCESS state", async () => {
    const { useTaskStatus } = await import("../../../hooks/useTaskStatus");
    (useTaskStatus as ReturnType<typeof vi.fn>).mockReturnValue({
      status: "SUCCESS",
      result: {
        success: true,
        total_rows: 15,
        success_count: 12,
        failed_count: 3,
        errors: [],
      },
      error: null,
      isTerminal: true,
    });
    render(<ImportProgressModal file={makeFile()} onClose={vi.fn()} />);
    expect(screen.getByText("Toplam")).toBeInTheDocument();
    expect(screen.getByText("Başarılı")).toBeInTheDocument();
    expect(screen.getByText("Atlandı")).toBeInTheDocument();
  });

  it("shows stat values in SUCCESS state", async () => {
    const { useTaskStatus } = await import("../../../hooks/useTaskStatus");
    (useTaskStatus as ReturnType<typeof vi.fn>).mockReturnValue({
      status: "SUCCESS",
      result: {
        success: true,
        total_rows: 15,
        success_count: 12,
        failed_count: 3,
        errors: [],
      },
      error: null,
      isTerminal: true,
    });
    render(<ImportProgressModal file={makeFile()} onClose={vi.fn()} />);
    expect(screen.getByText("15")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("shows partial success message when failed_count > 0", async () => {
    const { useTaskStatus } = await import("../../../hooks/useTaskStatus");
    (useTaskStatus as ReturnType<typeof vi.fn>).mockReturnValue({
      status: "SUCCESS",
      result: {
        success: true,
        total_rows: 10,
        success_count: 8,
        failed_count: 2,
        errors: [],
      },
      error: null,
      isTerminal: true,
    });
    render(<ImportProgressModal file={makeFile()} onClose={vi.fn()} />);
    expect(
      screen.getByText("Tamamlandı: 8 satır işlendi, 2 satır atlandı."),
    ).toBeInTheDocument();
  });

  it("shows Kapat button in SUCCESS state", async () => {
    const { useTaskStatus } = await import("../../../hooks/useTaskStatus");
    (useTaskStatus as ReturnType<typeof vi.fn>).mockReturnValue({
      status: "SUCCESS",
      result: {
        success: true,
        total_rows: 5,
        success_count: 5,
        failed_count: 0,
        errors: [],
      },
      error: null,
      isTerminal: true,
    });
    render(<ImportProgressModal file={makeFile()} onClose={vi.fn()} />);
    // "Kapat" appears as submit button at the bottom
    const kapatBtns = screen.getAllByText("Kapat");
    expect(kapatBtns.length).toBeGreaterThanOrEqual(1);
  });

  it("calls onClose when bottom Kapat button is clicked in SUCCESS", async () => {
    const { useTaskStatus } = await import("../../../hooks/useTaskStatus");
    (useTaskStatus as ReturnType<typeof vi.fn>).mockReturnValue({
      status: "SUCCESS",
      result: {
        success: true,
        total_rows: 5,
        success_count: 5,
        failed_count: 0,
        errors: [],
      },
      error: null,
      isTerminal: true,
    });
    const onClose = vi.fn();
    render(<ImportProgressModal file={makeFile()} onClose={onClose} />);
    // The bottom accent-colored "Kapat" button (not the X aria-label)
    const kapatBtns = screen.getAllByText("Kapat");
    // Find the styled submit-like button (bg-accent class)
    const accentBtn = kapatBtns.find((el) =>
      (el as HTMLElement).className.includes("bg-accent"),
    );
    fireEvent.click(accentBtn ?? kapatBtns[0]);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("shows startError when upload fails", async () => {
    const { tripService } = await import("../../../api/trips");
    (
      tripService.uploadExcelAsync as ReturnType<typeof vi.fn>
    ).mockRejectedValue({
      response: { data: { detail: "Dosya yüklenemedi." } },
    });
    render(<ImportProgressModal file={makeFile()} onClose={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByText("Dosya yüklenemedi.")).toBeInTheDocument();
    });
  });

  it("shows default start error when upload rejects without detail", async () => {
    const { tripService } = await import("../../../api/trips");
    (
      tripService.uploadExcelAsync as ReturnType<typeof vi.fn>
    ).mockRejectedValue(new Error("Network error"));
    render(<ImportProgressModal file={makeFile()} onClose={vi.fn()} />);
    await waitFor(() => {
      expect(
        screen.getByText("İçe aktarma başlatılamadı."),
      ).toBeInTheDocument();
    });
  });

  it("shows error list details in SUCCESS when errors present", async () => {
    const { useTaskStatus } = await import("../../../hooks/useTaskStatus");
    (useTaskStatus as ReturnType<typeof vi.fn>).mockReturnValue({
      status: "SUCCESS",
      result: {
        success: true,
        total_rows: 5,
        success_count: 4,
        failed_count: 1,
        errors: ["Satır 3: Plaka eksik", "Satır 5: Tarih formatı hatalı"],
      },
      error: null,
      isTerminal: true,
    });
    render(<ImportProgressModal file={makeFile()} onClose={vi.fn()} />);
    // details/summary element
    await waitFor(() => {
      expect(
        screen.getByText(
          (content) => content.includes("hata") && content.includes("toplam"),
        ),
      ).toBeInTheDocument();
    });
  });

  it("calls onComplete when SUCCESS with result", async () => {
    const { useTaskStatus } = await import("../../../hooks/useTaskStatus");
    const summaryResult = {
      success: true,
      total_rows: 5,
      success_count: 5,
      failed_count: 0,
      errors: [],
    };
    (useTaskStatus as ReturnType<typeof vi.fn>).mockReturnValue({
      status: "SUCCESS",
      result: summaryResult,
      error: null,
      isTerminal: true,
    });
    const onComplete = vi.fn();
    render(
      <ImportProgressModal
        file={makeFile()}
        onClose={vi.fn()}
        onComplete={onComplete}
      />,
    );
    await waitFor(() => {
      expect(onComplete).toHaveBeenCalledWith(summaryResult);
    });
  });
});
