/**
 * 0-mock epiği: TrailersModule'ın gerçek backend'e karşı senaryoları.
 *
 * `dorseService` (frontend/src/services/dorseService.ts) elle yazılmış —
 * axiosInstance.get("/trailers/...") gibi relative path'ler kullanıyor,
 * "/api/v1" prefix'i kendi içinde YOK. Bu yüzden `VITE_API_URL` gerçek
 * backend origin'i + "/api/v1" olmalı (`REAL_BACKEND_URL`) — orval-generated
 * client kullanmadığı için `REAL_BACKEND_ORIGIN` burada YANLIŞ olurdu (bkz
 * BreakdownReportModal.real-backend.test.tsx'teki double-prefix bug notu;
 * bu dosya o kategoriye girmiyor, karıştırılmamalı).
 *
 * Ortam neredeyse boş bir test DB'si olduğu ve paralel çalışan diğer
 * ajanların/test dosyalarının aynı `dorseler` tablosuna kayıt eklemesi/silmesi
 * mümkün olduğu için, toplam satır sayısına güvenen assertion'lar (ör. "tabloda
 * TAM OLARAK N kayıt var") KIRILGAN olur. Bunun yerine testler kendi
 * benzersiz (Date.now() suffix'li) plaka alt-string'ini `search` filtresiyle
 * izole ediyor — ambient DB durumundan bağımsız, deterministik.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";

vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
    tr: ({ children, ...rest }: any) => <tr {...rest}>{children}</tr>,
  },
}));

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("TrailersModule (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let TrailersModule: typeof import("../TrailersModule").TrailersModule;
  let trailerHeaderText: typeof import("../../../resources/tr/trailers").trailerHeaderText;
  let trailerTableText: typeof import("../../../resources/tr/trailers").trailerTableText;
  let trailerFilterText: typeof import("../../../resources/tr/trailers").trailerFilterText;
  let authToken: string;
  let uniqueTag: string;
  let dorseIdA: number;
  let dorseIdB: number;
  let plakaA: string;
  let plakaB: string;

  const authHeaders = () => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${authToken}`,
  });

  const createDorse = async (plaka: string) => {
    const resp = await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/trailers/`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        plaka,
        tipi: "Tenteli",
        bos_agirlik_kg: 7000.0,
        maks_yuk_kapasitesi_kg: 27000,
        lastik_sayisi: 6,
        aktif: true,
      }),
    });
    const created = await resp.json();
    return Number(created.data.id);
  };

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor, fireEvent } = await import(
      "../../../test/test-utils"
    ));
    ({ TrailersModule } = await import("../TrailersModule"));
    ({ trailerHeaderText, trailerTableText, trailerFilterText } = await import(
      "../../../resources/tr/trailers"
    ));

    uniqueTag = `ZZ${Date.now() % 100000}`;
    plakaA = `${uniqueTag}A`;
    plakaB = `${uniqueTag}B`;
    dorseIdA = await createDorse(plakaA);
    dorseIdB = await createDorse(plakaB);
  });

  afterAll(async () => {
    for (const id of [dorseIdA, dorseIdB]) {
      if (id) {
        await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/trailers/${id}`, {
          method: "DELETE",
          headers: authHeaders(),
        }).catch(() => {});
      }
    }
    vi.unstubAllEnvs();
  });

  const renderModule = async () => {
    sessionStorage.setItem("access_token", authToken);
    const result = render(<TrailersModule />);
    // Search'e geçmeden önce ilk (search="") sorgunun ayarlanmasını bekle —
    // aksi halde search-değişikliği ilk sorgu hâlâ uçuşurken tetiklenir ve
    // React Query'nin queryKey geçişi 10s'lik waitFor'u aşabilecek kadar
    // yavaşlayabiliyor (gerçek bir prod bug değil, test-timing race'i).
    await waitFor(() => {
      expect(screen.getByText(trailerHeaderText.addButton)).toBeInTheDocument();
    });
    return result;
  };

  const searchFor = (term: string) => {
    fireEvent.change(
      screen.getByPlaceholderText(trailerFilterText.searchPlaceholder),
      { target: { value: term } },
    );
  };

  it("renders the Add Trailer button", async () => {
    await renderModule();
    await waitFor(() => {
      expect(screen.getByText(trailerHeaderText.addButton)).toBeInTheDocument();
    });
  });

  it("shows header description", async () => {
    await renderModule();
    await waitFor(() => {
      expect(
        screen.getByText(trailerHeaderText.description),
      ).toBeInTheDocument();
    });
  });

  it("shows the real, just-created trailer plates after filtering to our unique tag", async () => {
    await renderModule();
    searchFor(uniqueTag);
    await waitFor(
      () => {
        expect(screen.getByText(plakaA)).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
    expect(screen.getByText(plakaB)).toBeInTheDocument();
  }, 15000);

  it("shows the fleet table title once real data is loaded", async () => {
    await renderModule();
    searchFor(uniqueTag);
    await waitFor(
      () => {
        expect(screen.getByText(trailerTableText.title)).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  }, 15000);

  it("shows total count reflecting the real, filtered backend result (2)", async () => {
    await renderModule();
    searchFor(uniqueTag);
    await waitFor(
      () => {
        expect(
          screen.getByText(trailerTableText.totalCount(2)),
        ).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  }, 15000);

  it("shows empty state for a search term with no real backend matches", async () => {
    await renderModule();
    searchFor(`${uniqueTag}NOPE`);
    await waitFor(
      () => {
        expect(
          screen.getByText(trailerTableText.emptyTitle),
        ).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  }, 15000);

  it("does NOT render pagination for our 2-item filtered result (below threshold of 8)", async () => {
    await renderModule();
    searchFor(uniqueTag);
    await waitFor(
      () => {
        expect(screen.getByText(plakaA)).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
    expect(
      screen.queryAllByRole("button", { name: /Önceki|Sonraki/ }),
    ).toHaveLength(0);
  }, 15000);
});
