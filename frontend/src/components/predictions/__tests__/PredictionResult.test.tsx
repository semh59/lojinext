import { describe, expect, it } from "vitest";
import { render, screen } from "../../../test/test-utils";
import { PredictionResult } from "../PredictionResult";

describe("PredictionResult", () => {
  it("tüketim, toplam litre ve maliyet projeksiyonu hesaplar", () => {
    render(
      <PredictionResult
        result={{
          tahmini_tuketim: 30,
          model_used: "ensemble",
        }}
        mesafeKm={200}
        unitPriceTL={40}
      />,
    );

    // 30 L/100km × 200km = 60 L → 60 × 40 = 2400 ₺
    expect(screen.getByText("30.0 L/100km")).toBeInTheDocument();
    expect(screen.getByText(/60 L/)).toBeInTheDocument();
    // Türkçe currency format ₺ ile, virgüllü/binlik ayraç olabilir
    expect(screen.getByText(/2\.?400/)).toBeInTheDocument();
  });

  it('güven aralığı yoksa "—" gösterir', () => {
    render(
      <PredictionResult
        result={{ tahmini_tuketim: 32, model_used: "linear" }}
        mesafeKm={100}
      />,
    );
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("güven aralığı varsa yüzde + min-max gösterir", () => {
    render(
      <PredictionResult
        result={{
          tahmini_tuketim: 30,
          model_used: "ensemble",
          confidence_low: 28,
          confidence_high: 32,
        }}
        mesafeKm={100}
      />,
    );
    // range = 4, tuketim*2 = 60 → ratio = 1 - 4/60 = 0.93 → %93
    expect(screen.getByText(/%9[23]/)).toBeInTheDocument();
    expect(screen.getByText(/28\.0 – 32\.0/)).toBeInTheDocument();
  });
});
