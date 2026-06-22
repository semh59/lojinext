import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../test/test-utils";

vi.mock("../../api/reports-studio", () => ({
  reportsStudioService: { listTemplates: vi.fn() },
}));

vi.mock("../../services/api", () => ({
  reportsApi: {
    downloadPdf: vi.fn(),
    downloadExcel: vi.fn(),
  },
  executiveApi: {
    downloadPdf: vi.fn(),
  },
}));

import { reportsStudioService } from "../../api/reports-studio";
import { executiveApi, reportsApi } from "../../services/api";
import ReportsStudioPage from "../ReportsStudioPage";

const sampleResponse = {
  count: 6,
  templates: [
    {
      id: "ceo_1pager" as const,
      title: "CEO 1-Pager",
      description: "Test desc",
      category: "executive" as const,
      formats: ["pdf" as const],
      endpoint_hint: "/reports/executive/pdf",
      supports_period: false,
      supports_vehicle: false,
    },
    {
      id: "fleet_weekly" as const,
      title: "Filo Haftalık",
      description: "Haftalık özet",
      category: "fleet" as const,
      formats: ["pdf" as const, "excel" as const],
      endpoint_hint: "/advanced-reports/pdf/fleet-summary",
      supports_period: true,
      supports_vehicle: false,
    },
    {
      id: "fuel_cost_analysis" as const,
      title: "Yakıt Maliyet",
      description: "Aylık",
      category: "fuel" as const,
      formats: ["pdf" as const, "excel" as const],
      endpoint_hint: "/advanced-reports/cost/period",
      supports_period: true,
      supports_vehicle: true,
    },
    {
      id: "vehicle_comparison" as const,
      title: "Araç Karşılaştırma",
      description: "Filo",
      category: "fleet" as const,
      formats: ["pdf" as const, "excel" as const],
      endpoint_hint: "/reports/vehicle-comparison",
      supports_period: true,
      supports_vehicle: false,
    },
    {
      id: "carbon_report" as const,
      title: "Karbon",
      description: "12 ay",
      category: "compliance" as const,
      formats: ["pdf" as const, "excel" as const],
      endpoint_hint: "/reports/executive/carbon",
      supports_period: true,
      supports_vehicle: false,
    },
    {
      id: "what_if" as const,
      title: "What-If",
      description: "Senaryo",
      category: "executive" as const,
      formats: ["pdf" as const],
      endpoint_hint: "/reports/executive/what-if/export",
      supports_period: false,
      supports_vehicle: false,
    },
  ],
};

describe("ReportsStudioPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // jsdom blob/url stubs
    if (!window.URL.createObjectURL) {
      window.URL.createObjectURL = vi.fn(() => "blob:mock");
    }
    if (!window.URL.revokeObjectURL) {
      window.URL.revokeObjectURL = vi.fn();
    }
  });

  it("happy path: 6 sablon karti gorunur", async () => {
    (
      reportsStudioService.listTemplates as ReturnType<typeof vi.fn>
    ).mockResolvedValue(sampleResponse);

    render(<ReportsStudioPage />);
    await waitFor(() =>
      expect(screen.getByText("CEO 1-Pager")).toBeInTheDocument(),
    );
    expect(screen.getByText("Filo Haftalık")).toBeInTheDocument();
    expect(screen.getByText("Yakıt Maliyet")).toBeInTheDocument();
    expect(screen.getByText("Araç Karşılaştırma")).toBeInTheDocument();
    expect(screen.getByText("Karbon")).toBeInTheDocument();
    expect(screen.getByText("What-If")).toBeInTheDocument();
  });

  it("kart secimi: konfigurasyon paneli acilir", async () => {
    (
      reportsStudioService.listTemplates as ReturnType<typeof vi.fn>
    ).mockResolvedValue(sampleResponse);

    render(<ReportsStudioPage />);
    await waitFor(() => screen.getByText("Filo Haftalık"));

    // Başlangıçta hint görünür
    expect(screen.getByTestId("config-empty")).toBeInTheDocument();

    // Kartı tıkla
    fireEvent.click(screen.getByTestId("template-card-fleet_weekly"));

    // Empty hint kayboldu, period select göründü
    expect(screen.queryByTestId("config-empty")).not.toBeInTheDocument();
    expect(screen.getByTestId("period-select")).toBeInTheDocument();
    expect(screen.getByTestId("format-pdf")).toBeInTheDocument();
    expect(screen.getByTestId("format-excel")).toBeInTheDocument();
  });

  it("CEO PDF: executiveApi.downloadPdf cagrilir", async () => {
    (
      reportsStudioService.listTemplates as ReturnType<typeof vi.fn>
    ).mockResolvedValue(sampleResponse);
    (executiveApi.downloadPdf as ReturnType<typeof vi.fn>).mockResolvedValue(
      undefined,
    );

    render(<ReportsStudioPage />);
    await waitFor(() => screen.getByText("CEO 1-Pager"));

    fireEvent.click(screen.getByTestId("template-card-ceo_1pager"));
    fireEvent.click(screen.getByTestId("download-button"));

    await waitFor(() => {
      expect(executiveApi.downloadPdf).toHaveBeenCalledTimes(1);
    });
    // Success feedback
    await waitFor(() =>
      expect(screen.getByTestId("feedback-success")).toBeInTheDocument(),
    );
  });

  it("Filo Haftalik Excel: reportsApi.downloadExcel cagrilir", async () => {
    (
      reportsStudioService.listTemplates as ReturnType<typeof vi.fn>
    ).mockResolvedValue(sampleResponse);
    (reportsApi.downloadExcel as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Blob(["x"], { type: "application/vnd.ms-excel" }),
    );

    render(<ReportsStudioPage />);
    await waitFor(() => screen.getByText("Filo Haftalık"));

    fireEvent.click(screen.getByTestId("template-card-fleet_weekly"));
    fireEvent.click(screen.getByTestId("format-excel"));
    fireEvent.click(screen.getByTestId("download-button"));

    await waitFor(() => {
      expect(reportsApi.downloadExcel).toHaveBeenCalledTimes(1);
      expect(reportsApi.downloadExcel).toHaveBeenCalledWith(
        "fleet_summary",
        expect.objectContaining({ start_date: expect.any(String) }),
      );
    });
  });

  it("Indirme hatasi: feedback-error gorunur", async () => {
    (
      reportsStudioService.listTemplates as ReturnType<typeof vi.fn>
    ).mockResolvedValue(sampleResponse);
    (executiveApi.downloadPdf as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("network"),
    );

    render(<ReportsStudioPage />);
    await waitFor(() => screen.getByText("CEO 1-Pager"));

    fireEvent.click(screen.getByTestId("template-card-ceo_1pager"));
    fireEvent.click(screen.getByTestId("download-button"));

    await waitFor(() =>
      expect(screen.getByTestId("feedback-error")).toBeInTheDocument(),
    );
  });

  it("Galeri hata durumu: gallery-error gorunur", async () => {
    (
      reportsStudioService.listTemplates as ReturnType<typeof vi.fn>
    ).mockRejectedValue(new Error("boom"));

    render(<ReportsStudioPage />);
    await waitFor(() =>
      expect(screen.getByTestId("gallery-error")).toBeInTheDocument(),
    );
  });
});
