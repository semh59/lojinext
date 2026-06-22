import { describe, expect, it, vi } from "vitest";

import { render, screen } from "../../../test/test-utils";
import { TelemetrySection } from "../TelemetrySection";
import { TripList } from "../TripList";

vi.mock("../../weather/WeatherAnalysisCard", () => ({
  WeatherAnalysisCard: () => <div data-testid="weather-analysis-card" />,
}));

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
}));

describe("Trip surface resource-only rendering", () => {
  it("renders telemetry empty state from shared resources", () => {
    render(
      <TelemetrySection
        watchedGuzergahId=""
        watchedCikis=""
        watchedVaris=""
        watchedMesafe={0}
        weatherImpact={null}
        weatherLoading={false}
        errors={{} as any}
      />,
    );

    expect(screen.getByText(/güzergâh verisi bekleniyor/i)).toBeInTheDocument();
    expect(
      screen.getByText(/telemetri analizi için lütfen üst menüden/i),
    ).toBeInTheDocument();
    expect(screen.getByTestId("weather-analysis-card")).toBeInTheDocument();
  });

  it("renders trip list empty state from shared resources", () => {
    render(<TripList trips={[]} onSelect={vi.fn()} loading={false} />);

    expect(screen.getByText(/aktif sefer yok/i)).toBeInTheDocument();
    expect(
      screen.getByText(/planlanan bir sefer bulunmuyor/i),
    ).toBeInTheDocument();
  });
});
