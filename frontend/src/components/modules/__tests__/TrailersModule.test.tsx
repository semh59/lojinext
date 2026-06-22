import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";
import { TrailersModule } from "../TrailersModule";
import {
  trailerHeaderText,
  trailerTableText,
} from "../../../resources/tr/trailers";
import { Dorse } from "../../../types";

// framer-motion passthrough
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
    tr: ({ children, ...rest }: any) => <tr {...rest}>{children}</tr>,
  },
}));

// Mock dorseService
vi.mock("../../../services/dorseService", () => ({
  dorseService: {
    getAll: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    exportExcel: vi.fn(),
    downloadTemplate: vi.fn(),
    uploadExcel: vi.fn(),
  },
}));

// Mock use-url-state
vi.mock("../../../hooks/use-url-state", () => ({
  useUrlState: (initial: any) => [initial, vi.fn()],
}));

// Mock NotificationContext
vi.mock("../../../context/NotificationContext", () => ({
  useNotify: () => ({ notify: vi.fn() }),
  NotificationProvider: ({ children }: any) => <>{children}</>,
}));

const MOCK_TRAILERS: Dorse[] = [
  {
    id: 1,
    plaka: "34TRL001",
    marka: "Krone",
    tipi: "Frigo",
    yil: 2021,
    bos_agirlik_kg: 7000,
    maks_yuk_kapasitesi_kg: 22000,
    lastik_sayisi: 8,
    aktif: true,
    notlar: null,
  },
  {
    id: 2,
    plaka: "06TRL002",
    marka: "Tırsan",
    tipi: "Standart",
    yil: 2019,
    bos_agirlik_kg: 6500,
    maks_yuk_kapasitesi_kg: 24000,
    lastik_sayisi: 6,
    aktif: false,
    notlar: null,
  },
];

describe("TrailersModule", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const { dorseService } = await import("../../../services/dorseService");
    (dorseService.getAll as ReturnType<typeof vi.fn>).mockResolvedValue(
      MOCK_TRAILERS,
    );
  });

  it("renders the Add Trailer button", async () => {
    render(<TrailersModule />);
    await waitFor(() => {
      expect(screen.getByText(trailerHeaderText.addButton)).toBeInTheDocument();
    });
  });

  it("shows trailer plates after data loads", async () => {
    render(<TrailersModule />);
    await waitFor(() => {
      expect(screen.getByText("34TRL001")).toBeInTheDocument();
    });
    expect(screen.getByText("06TRL002")).toBeInTheDocument();
  });

  it("shows the fleet table title", async () => {
    render(<TrailersModule />);
    await waitFor(() => {
      expect(screen.getByText(trailerTableText.title)).toBeInTheDocument();
    });
  });

  it("shows total count when trailers are loaded", async () => {
    render(<TrailersModule />);
    await waitFor(() => {
      expect(
        screen.getByText(trailerTableText.totalCount(2)),
      ).toBeInTheDocument();
    });
  });

  it("shows empty state when service returns no trailers", async () => {
    const { dorseService } = await import("../../../services/dorseService");
    (dorseService.getAll as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    render(<TrailersModule />);
    await waitFor(() => {
      expect(screen.getByText(trailerTableText.emptyTitle)).toBeInTheDocument();
    });
  });

  it("does NOT render pagination for 2 items (below threshold of 8)", async () => {
    render(<TrailersModule />);
    await waitFor(() => {
      expect(screen.getByText("34TRL001")).toBeInTheDocument();
    });
    // totalPages=1 — no prev/next buttons rendered
    expect(
      screen.queryByText(
        (trailerTableText as any).pagination
          ? (trailerTableText as any).pagination?.previous
          : "Önceki",
      ),
    ).not.toBeInTheDocument();
  });

  it("shows header description", async () => {
    render(<TrailersModule />);
    await waitFor(() => {
      expect(
        screen.getByText(trailerHeaderText.description),
      ).toBeInTheDocument();
    });
  });
});
