/**
 * 0-mock epiği: ReportsStudioPage'in şablon galerisi (`GET /reports/studio/
 * templates`) statik/deterministik bir konfig listesi döndürüyor (DB seed'e
 * bağlı değil) — bu yüzden `vi.mock("../../api/reports-studio")` kaldırıldı,
 * gerçek backend'e karşı çalışıyor. İndirme dispatch'i (`reportsApi`/
 * `executiveApi` — PDF/Excel binary üretimi) hâlâ mock'lu: bu, "kartı seç →
 * doğru servis fonksiyonu doğru argümanlarla çağrılır" akışını test ediyor,
 * gerçek PDF/Excel üretimi ayrı bir endişe (backend'in kendi PDF/Excel
 * testleri zaten kapsıyor).
 *
 * DÜŞÜRÜLEN SENARYO: orijinal mock'lu dosyadaki "Galeri hata durumu:
 * gallery-error görünür" testi (`listTemplates` reject) buraya taşınmadı —
 * gerçek, sağlıklı bir backend'e karşı bu 500/network-hata durumunu
 * tetiklemenin güvenilir bir yolu yok (endpoint stub'ları yalnız dış API'ler
 * için var, dahili backend değil); component'in kendi hata-render mantığı
 * zaten kanıtlı, E2E veya gelecekte bir backend-down entegrasyon testinin
 * kapsamı.
 */
import {
  describe,
  expect,
  it,
  vi,
  beforeAll,
  afterAll,
  beforeEach,
} from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../test/real-backend";

vi.mock("../../services/api", () => ({
  reportsApi: {
    downloadPdf: vi.fn(),
    downloadExcel: vi.fn(),
  },
  executiveApi: {
    downloadPdf: vi.fn(),
  },
}));

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("ReportsStudioPage (real backend)", () => {
  let render: typeof import("../../test/test-utils").render;
  let screen: typeof import("../../test/test-utils").screen;
  let fireEvent: typeof import("../../test/test-utils").fireEvent;
  let waitFor: typeof import("../../test/test-utils").waitFor;
  let executiveApi: typeof import("../../services/api").executiveApi;
  let reportsApi: typeof import("../../services/api").reportsApi;
  let ReportsStudioPage: typeof import("../ReportsStudioPage").default;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ render, screen, fireEvent, waitFor } = await import(
      "../../test/test-utils"
    ));
    ({ executiveApi, reportsApi } = await import("../../services/api"));
    ({ default: ReportsStudioPage } = await import("../ReportsStudioPage"));
  }, 20000);

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  beforeEach(async () => {
    vi.clearAllMocks();
    sessionStorage.setItem("access_token", await loginAsAdmin());
    if (!window.URL.createObjectURL) {
      window.URL.createObjectURL = vi.fn(() => "blob:mock");
    }
    if (!window.URL.revokeObjectURL) {
      window.URL.revokeObjectURL = vi.fn();
    }
  });

  it("happy path: gerçek backend'den 6 şablon kartı gelir", async () => {
    render(<ReportsStudioPage />);
    await waitFor(
      () => expect(screen.getByText(/CEO.*1-Pager/i)).toBeInTheDocument(),
      { timeout: 15000 },
    );
    expect(screen.getByText(/Filo.*Haftalık/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Yakıt Maliyet/i)[0]).toBeInTheDocument();
    expect(screen.getByText("Araç Karşılaştırma")).toBeInTheDocument();
    expect(screen.getByText("Karbon Raporu")).toBeInTheDocument();
    expect(screen.getByText(/What-If/i)).toBeInTheDocument();
  }, 20000);

  it("kart seçimi: konfigürasyon paneli açılır", async () => {
    render(<ReportsStudioPage />);
    await waitFor(() => screen.getByText(/Filo.*Haftalık/i), {
      timeout: 15000,
    });

    expect(screen.getByTestId("config-empty")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("template-card-fleet_weekly"));

    expect(screen.queryByTestId("config-empty")).not.toBeInTheDocument();
    expect(screen.getByTestId("period-select")).toBeInTheDocument();
    expect(screen.getByTestId("format-pdf")).toBeInTheDocument();
    expect(screen.getByTestId("format-excel")).toBeInTheDocument();
  }, 20000);

  it("CEO PDF: executiveApi.downloadPdf çağrılır", async () => {
    (executiveApi.downloadPdf as ReturnType<typeof vi.fn>).mockResolvedValue(
      undefined,
    );

    render(<ReportsStudioPage />);
    await waitFor(() => screen.getByText(/CEO.*1-Pager/i), {
      timeout: 15000,
    });

    fireEvent.click(screen.getByTestId("template-card-ceo_1pager"));
    fireEvent.click(screen.getByTestId("download-button"));

    await waitFor(() => {
      expect(executiveApi.downloadPdf).toHaveBeenCalledTimes(1);
    });
    await waitFor(() =>
      expect(screen.getByTestId("feedback-success")).toBeInTheDocument(),
    );
  }, 20000);

  it("Filo Haftalık Excel: reportsApi.downloadExcel çağrılır", async () => {
    (reportsApi.downloadExcel as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Blob(["x"], { type: "application/vnd.ms-excel" }),
    );

    render(<ReportsStudioPage />);
    await waitFor(() => screen.getByText(/Filo.*Haftalık/i), {
      timeout: 15000,
    });

    fireEvent.click(screen.getByTestId("template-card-fleet_weekly"));
    fireEvent.click(screen.getByTestId("format-excel"));
    fireEvent.click(screen.getByTestId("download-button"));

    await waitFor(() => {
      expect(reportsApi.downloadExcel).toHaveBeenCalledTimes(1);
      expect(reportsApi.downloadExcel).toHaveBeenCalledWith(
        "fleet_summary",
        expect.objectContaining({ start_date: expect.any(String) }),
      );
    });
  }, 20000);

  it("Araç Karşılaştırma PDF: reportsApi.downloadPdf 'vehicle_comparison' ile çağrılır", async () => {
    // Regression: bu şablon eskiden "vehicle_detail" (id zorunlu, tek-araç
    // detay rotası) çağırıyordu → backend'de id'siz karşılığı yoktu, 404.
    // Artık gerçek çoklu-araç karşılaştırma tipini kullanıyor.
    (reportsApi.downloadPdf as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Blob(["x"], { type: "application/pdf" }),
    );

    render(<ReportsStudioPage />);
    await waitFor(() => screen.getByText("Araç Karşılaştırma"), {
      timeout: 15000,
    });

    fireEvent.click(screen.getByTestId("template-card-vehicle_comparison"));
    fireEvent.click(screen.getByTestId("download-button"));

    await waitFor(() => {
      expect(reportsApi.downloadPdf).toHaveBeenCalledTimes(1);
      expect(reportsApi.downloadPdf).toHaveBeenCalledWith(
        "vehicle_comparison",
        undefined,
        expect.any(Object),
      );
    });
  }, 20000);

  it("Araç Karşılaştırma Excel: reportsApi.downloadExcel 'vehicle_comparison' ile çağrılır", async () => {
    // Regression: eskiden "vehicle_report" gönderiyordu → backend'in
    // /excel/export'u bu tipi tanımıyordu, 400.
    (reportsApi.downloadExcel as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Blob(["x"], { type: "application/vnd.ms-excel" }),
    );

    render(<ReportsStudioPage />);
    await waitFor(() => screen.getByText("Araç Karşılaştırma"), {
      timeout: 15000,
    });

    fireEvent.click(screen.getByTestId("template-card-vehicle_comparison"));
    fireEvent.click(screen.getByTestId("format-excel"));
    fireEvent.click(screen.getByTestId("download-button"));

    await waitFor(() => {
      expect(reportsApi.downloadExcel).toHaveBeenCalledTimes(1);
      expect(reportsApi.downloadExcel).toHaveBeenCalledWith(
        "vehicle_comparison",
        expect.any(Object),
      );
    });
  }, 20000);

  it("İndirme hatası: feedback-error görünür", async () => {
    (executiveApi.downloadPdf as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("network"),
    );

    render(<ReportsStudioPage />);
    await waitFor(() => screen.getByText(/CEO.*1-Pager/i), {
      timeout: 15000,
    });

    fireEvent.click(screen.getByTestId("template-card-ceo_1pager"));
    fireEvent.click(screen.getByTestId("download-button"));

    await waitFor(() =>
      expect(screen.getByTestId("feedback-error")).toBeInTheDocument(),
    );
  }, 20000);
});
