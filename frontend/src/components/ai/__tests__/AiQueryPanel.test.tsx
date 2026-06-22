import { describe, expect, it, vi } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { render } from "../../../test/test-utils";

vi.mock("../../../api/ai", () => ({
  aiApi: {
    query: vi.fn().mockResolvedValue({
      category: "fuel_trend",
      answer: "Trend yukarı.",
      chart: {
        type: "line",
        title: "Aylık Yakıt Maliyeti (TL)",
        x_key: "ay",
        series: [{ key: "tutar", label: "Toplam Tutar" }],
        data: [
          { ay: "2026-01", tutar: 4000 },
          { ay: "2026-02", tutar: 5000 },
        ],
      },
      actions: [{ label: "Yakıt sayfası", url: "/fuel" }],
    }),
  },
}));

describe("AiQueryPanel", () => {
  it("runs a query and renders answer, chart title and action link", async () => {
    const { AiQueryPanel } = await import("../AiQueryPanel");
    render(<AiQueryPanel />);
    fireEvent.change(screen.getByPlaceholderText(/sor/i), {
      target: { value: "yakıt trendi" },
    });
    fireEvent.click(screen.getByText("Sorgula"));
    expect(await screen.findByText("Trend yukarı.")).toBeInTheDocument();
    expect(screen.getByText(/Aylık Yakıt Maliyeti/)).toBeInTheDocument();
    const link = screen.getByText(/Yakıt sayfası/).closest("a");
    expect(link).toHaveAttribute("href", "/fuel");
  });
});
