import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "../../../test/test-utils";

import { RouteAnalysisCard } from "../RouteAnalysisCard";

vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactNode }) => (
      <div style={{ width: 480, height: 320 }}>{children}</div>
    ),
  };
});

describe("RouteAnalysisCard", () => {
  it("renders correctly with complete analysis data", () => {
    const mockAnalysis = {
      highway: { flat: 100, up: 20, down: 10 },
      other: { flat: 50, up: 5, down: 5 },
    };

    render(<RouteAnalysisCard analysis={mockAnalysis as any} />);

    expect(screen.getByText(/Güzergah Özeti/i)).toBeInTheDocument();
    expect(screen.getByText(/Düz/i)).toBeInTheDocument();
    expect(screen.getByText(/150.0 km/i)).toBeInTheDocument();
  });

  it("renders gracefully with partial analysis data", () => {
    const partialAnalysis = {
      highway: { flat: 100 },
    };

    render(<RouteAnalysisCard analysis={partialAnalysis as any} />);

    expect(screen.getByText(/Güzergah Özeti/i)).toBeInTheDocument();
    expect(screen.getByText(/100.0 km/i)).toBeInTheDocument();
  });

  it("handles empty analysis without crashing", () => {
    render(<RouteAnalysisCard analysis={{} as any} />);
    expect(screen.getByText(/Güzergah Özeti/i)).toBeInTheDocument();
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
  });
});
