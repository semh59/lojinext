import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "../../../test/test-utils";

vi.mock("../../../api/analytics", () => ({
  fetchPageViewStats: vi.fn().mockResolvedValue({
    period_days: 30,
    total_views: 42,
    top_routes: [{ route: "/trips", count: 30 }],
    bottom_routes: [{ route: "/profile", count: 1 }],
  }),
}));

describe("AnalyticsPage", () => {
  it("renders top and bottom routes from the API", async () => {
    const { default: AnalyticsPage } = await import("../AnalyticsPage");
    render(<AnalyticsPage />);
    expect(await screen.findByText("/trips")).toBeInTheDocument();
    expect(await screen.findByText("/profile")).toBeInTheDocument();
    expect(screen.getByText(/42/)).toBeInTheDocument();
  });
});
