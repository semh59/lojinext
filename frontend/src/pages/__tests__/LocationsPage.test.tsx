import { describe, expect, it, vi } from "vitest";
import { render, screen } from "../../test/test-utils";

import LocationsPage from "../LocationsPage";

vi.mock("../../hooks/use-url-state", () => ({
  useUrlState: () => [{ search: "", zorluk: "", page: 1 }, vi.fn()],
}));

vi.mock("../../hooks/use-locations", () => ({
  useLocations: () => ({
    useGetLocations: () => ({
      data: {
        items: [
          {
            id: 1,
            cikis_yeri: "İstanbul",
            varis_yeri: "Ankara",
            mesafe_km: 450,
            zorluk: "Zor",
            route_analysis: {
              highway: { flat: 10, up: 2, down: 1 },
              other: { flat: 5, up: 1, down: 1 },
            },
          },
        ],
        total: 1,
      },
      isLoading: false,
      isFetching: false,
      refetch: vi.fn(),
    }),
    useCreateLocation: () => ({ mutateAsync: vi.fn() }),
    useUpdateLocation: () => ({ mutateAsync: vi.fn() }),
    useDeleteLocation: () => ({ mutateAsync: vi.fn() }),
  }),
}));

vi.mock("../../components/locations/LocationList", () => ({
  LocationList: () => <div>Location list</div>,
}));

vi.mock("../../components/locations/LocationFormModal", () => ({
  LocationFormModal: () => null,
}));

vi.mock("../../components/locations/AnalysisModal", () => ({
  AnalysisModal: () => null,
}));

vi.mock("../../components/shared/DataExportImport", () => ({
  DataExportImport: () => <div>toolbar</div>,
}));

vi.mock("../../api/locations", () => ({
  locationService: {
    analyze: vi.fn(),
    downloadTemplate: vi.fn(),
    exportExcel: vi.fn(),
    uploadExcel: vi.fn(),
  },
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe("LocationsPage", () => {
  it("renders truthful operational copy and removes simulated map language", () => {
    render(<LocationsPage />);

    expect(screen.getByText(/Operasyonel Görünürlük/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Canlı harita veya simüle telemetri kullanılmaz/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Map Simulation/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Canlı Şebeke Analizi/i)).not.toBeInTheDocument();
  });
});
