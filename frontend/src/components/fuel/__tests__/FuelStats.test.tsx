import { render, screen } from "../../../test/test-utils";
import { FuelStats } from "../FuelStats";

describe("FuelStats", () => {
  it("renders a truthful unavailable state when stats are missing", () => {
    render(<FuelStats stats={null} loading={false} />);

    expect(
      screen.getByText(
        "Yakıt istatistikleri şu anda alınamıyor. Gerçek veri gelmeden özet kartları gösterilmiyor.",
      ),
    ).toBeInTheDocument();
  });

  it("toplam mesafe ve yakıt anomalisi dahil 6 kartı göstermeli", () => {
    render(
      <FuelStats
        loading={false}
        stats={{
          total_consumption: 1200,
          total_cost: 90000,
          avg_consumption: 31.5,
          avg_price: 42.5,
          total_distance: 4200,
        }}
      />,
    );

    expect(screen.getByText("Toplam Tüketim")).toBeInTheDocument();
    expect(screen.getByText("Toplam Maliyet")).toBeInTheDocument();
    expect(screen.getByText("Ortalama Tüketim")).toBeInTheDocument();
    expect(screen.getByText("Ortalama Fiyat")).toBeInTheDocument();
    expect(screen.getByText("Toplam Mesafe")).toBeInTheDocument();
    expect(screen.getByText("Yakıt Anomalisi")).toBeInTheDocument();
    expect(screen.getByText(/4\.?200 km/)).toBeInTheDocument();
  });
});
