import { describe, expect, it, vi } from "vitest";
import { render, screen } from "../../../../test/test-utils";
import { InspectionTab } from "../InspectionTab";

vi.mock("@/services/api/axios-instance", () => ({
  default: {
    get: vi.fn().mockResolvedValue({
      data: {
        expiring: [
          {
            id: 1,
            plaka: "34 A 1",
            marka: "MAN",
            muayene_tarihi: "2026-07-12",
            days_remaining: 17,
          },
        ],
        overdue: [],
      },
    }),
  },
}));

describe("InspectionTab", () => {
  it("renders vehicle + trailer inspection sections", () => {
    render(<InspectionTab />);
    expect(screen.getByText("Araçlar")).toBeInTheDocument();
    expect(screen.getByText("Dorseler")).toBeInTheDocument();
  });

  it("shows an expiring inspection row", async () => {
    render(<InspectionTab />);
    expect(await screen.findAllByText("34 A 1")).not.toHaveLength(0);
  });
});
