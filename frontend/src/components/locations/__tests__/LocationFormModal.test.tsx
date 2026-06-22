import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "../../../test/test-utils";

import { locationService } from "../../../api/locations";
import { LocationFormModal } from "../LocationFormModal";

vi.mock("../../../api/locations", () => ({
  locationService: {
    geocode: vi.fn(),
    getRouteInfo: vi.fn(),
  },
}));

vi.mock("../../../hooks/useDebounce", () => ({
  useDebounce: (value: string) => value,
}));

vi.mock("../../ui/Modal", () => ({
  Modal: ({ children, isOpen, title }: any) =>
    isOpen ? (
      <div role="dialog" aria-label={title ?? "location-modal"}>
        {children}
      </div>
    ) : null,
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe("LocationFormModal", () => {
  it("geocodes both addresses and auto-calculates route details after selection", async () => {
    vi.clearAllMocks();
    vi.mocked(locationService.geocode).mockImplementation(
      async (query: string) => {
        if (query.toLowerCase().includes("hadimkoy")) {
          return [
            {
              lat: 41.07,
              lon: 28.54,
              label: "Hadimkoy Lojistik",
              source: "ors",
            },
          ] as any;
        }
        if (query.toLowerCase().includes("ostim")) {
          return [
            { lat: 39.96, lon: 32.74, label: "Ostim Fabrika", source: "ors" },
          ] as any;
        }
        return [] as any;
      },
    );

    vi.mocked(locationService.getRouteInfo).mockResolvedValue({
      distance_km: 410,
      duration_min: 330,
      difficulty: "Normal",
      ascent_m: 320,
      descent_m: 280,
      flat_distance_km: 360,
      otoban_mesafe_km: 290,
      sehir_ici_mesafe_km: 120,
      source: "api",
      route_analysis: {
        highway: { flat: 290, up: 0, down: 0 },
        other: { flat: 120, up: 0, down: 0 },
      },
    } as any);

    const user = userEvent.setup();

    render(
      <LocationFormModal
        isOpen
        onClose={vi.fn()}
        onSave={vi.fn()}
        location={null}
      />,
    );

    await act(async () => {
      fireEvent.change(screen.getByLabelText(/çıkış yeri arama/i), {
        target: { value: "Hadimkoy Lojistik" },
      });
    });
    await act(async () => {
      await user.click(
        await screen.findByRole("button", { name: /Hadimkoy Lojistik/i }),
      );
    });

    await act(async () => {
      fireEvent.change(screen.getByLabelText(/varış yeri arama/i), {
        target: { value: "Ostim Fabrika" },
      });
    });
    await act(async () => {
      await user.click(
        await screen.findByRole("button", { name: /Ostim Fabrika/i }),
      );
    });

    await waitFor(() => {
      expect(locationService.getRouteInfo).toHaveBeenCalledWith({
        cikis_lat: 41.07,
        cikis_lon: 28.54,
        varis_lat: 39.96,
        varis_lon: 32.74,
      });
    });

    await waitFor(() => {
      expect(screen.getByLabelText(/mesafe \(km\)/i)).toHaveValue(410);
    });
  });
});
