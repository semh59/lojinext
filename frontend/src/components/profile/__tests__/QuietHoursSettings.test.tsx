import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "../../../test/test-utils";

vi.mock("../../../api/preferences", () => ({
  preferenceService: {
    getPreferences: vi.fn().mockResolvedValue({
      items: [{ deger: { enabled: true, start: "22:00", end: "07:00" } }],
    }),
    savePreference: vi.fn().mockResolvedValue({}),
  },
}));

describe("QuietHoursSettings", () => {
  it("loads and shows the saved quiet hours", async () => {
    const { QuietHoursSettings } = await import("../QuietHoursSettings");
    render(<QuietHoursSettings />);
    expect(await screen.findByDisplayValue("22:00")).toBeInTheDocument();
    expect(screen.getByDisplayValue("07:00")).toBeInTheDocument();
  });
});
