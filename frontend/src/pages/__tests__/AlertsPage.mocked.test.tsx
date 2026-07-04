/**
 * 0-mock epiği notu: bu dosya bilinçli olarak mock'lu kalıyor. Fine-grained
 * senaryolar (fuel-gap>0, bakım adayı listesi, acknowledge/resolve akışı,
 * RCA/suggested-action alanları, tab-filtreleme) gerçek backend'e karşı
 * yeniden üretmek için `anomalies` + `seferler` + `araclar` + `soforler`
 * arasında çapraz-tablo sentetik veri seed'i gerektiriyor — maliyeti bu
 * testin katma değerine oranla aşırı yüksek. Cold-start/boş-state
 * (gerçek backend, seed'siz DB) varyantı `AlertsPage.test.tsx`'te
 * doğrulanıyor.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../test/test-utils";
import type {
  FleetInsightsData,
  RecentAnomaliesResponse,
} from "../../api/anomalies";
import AlertsPage from "../AlertsPage";

// framer-motion passthrough
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

// recharts stub — avoids SVG + ResizeObserver errors
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: any) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  BarChart: ({ children }: any) => <svg>{children}</svg>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}));

vi.mock("../../hooks/usePageTitle", () => ({ usePageTitle: vi.fn() }));

vi.mock("../../components/alerts/AnomalyTable", () => ({
  LeakageSummary: ({ leakage }: any) => (
    <div data-testid="leakage-summary">
      LeakageSummary:{leakage.fuel_gap_liters}
    </div>
  ),
  MaintenanceTable: ({ vehicles }: any) => (
    <div data-testid="maintenance-table">
      MaintenanceTable:{vehicles.length}
    </div>
  ),
}));

vi.mock("../../components/alerts/InvestigationsKanban", () => ({
  InvestigationsKanban: () => (
    <div data-testid="investigations-kanban">Kanban</div>
  ),
}));

vi.mock("../../components/alerts/PatternList", () => ({
  PatternList: () => <div data-testid="pattern-list">PatternList</div>,
}));

// Permission gate is exercised in the backend tests; here render its children
// so the anomaly action buttons (Onayla/Çöz) remain assertable.
vi.mock("../../components/auth/RequirePermission", () => ({
  RequirePermission: ({ children }: any) => <>{children}</>,
}));

vi.mock("../../api/anomalies", () => ({
  anomalyService: {
    getFleetInsights: vi.fn(),
    getRecentAnomalies: vi.fn(),
    acknowledge: vi.fn(),
    resolve: vi.fn(),
  },
}));

vi.mock("../../api/investigations", () => ({
  investigationService: {
    list: vi.fn(),
  },
}));

const INSIGHTS_CLEAN: FleetInsightsData = {
  leakage: {
    fuel_gap_liters: 0,
    route_deviation_km: 0,
    route_deviation_cost: 0,
    fuel_gap_cost: 0,
    total_leakage_cost: 0,
  },
  maintenance: {
    urgent_count: 0,
    warning_count: 0,
    vehicles: [],
  },
};

const INSIGHTS_ALERT: FleetInsightsData = {
  leakage: {
    fuel_gap_liters: 150,
    route_deviation_km: 25,
    route_deviation_cost: 500,
    fuel_gap_cost: 1200,
    total_leakage_cost: 1700,
  },
  maintenance: {
    urgent_count: 2,
    warning_count: 3,
    vehicles: [
      {
        id: 1,
        plaka: "06ABC01",
        reason: "Yağ değişimi",
        severity: "high" as const,
        toplam_km: 95000,
        ort_tuketim: 32,
      },
    ],
  },
};

const RECENT_EMPTY: RecentAnomaliesResponse = {
  anomalies: [],
  total: 0,
  filters: { days: 30, severity: null, tip: null },
};

const RECENT_DATA: RecentAnomaliesResponse = {
  anomalies: [
    {
      id: 1,
      tarih: "2026-06-01T10:00:00",
      tip: "tuketim",
      kaynak_tip: "sefer",
      kaynak_id: 42,
      deger: 45.5,
      beklenen_deger: 35.0,
      sapma_yuzde: 30.0,
      severity: "high" as const,
      aciklama: "Yakıt tüketimi beklenenin üzerinde",
      rca_summary: null,
      suggested_action: null,
      plaka: "34XYZ99",
      sofor_adi: "Ahmet Yılmaz",
      acknowledged_at: null,
      resolved_at: null,
      resolution_notes: null,
    },
    {
      id: 2,
      tarih: "2026-06-02T09:00:00",
      tip: "maliyet",
      kaynak_tip: "sefer",
      kaynak_id: 43,
      deger: 80.0,
      beklenen_deger: 60.0,
      sapma_yuzde: 33.3,
      severity: "critical" as const,
      aciklama: "Maliyet sapması kritik",
      rca_summary: "Uzun güzergah",
      suggested_action: "Güzergahı optimize edin",
      plaka: "06DEF55",
      sofor_adi: null,
      acknowledged_at: "2026-06-02T10:00:00",
      resolved_at: null,
      resolution_notes: null,
    },
  ],
  total: 2,
  filters: { days: 30, severity: null, tip: null },
};

async function setupMocks(
  insights = INSIGHTS_CLEAN,
  recent = RECENT_EMPTY,
  investigations: any[] = [],
) {
  const { anomalyService } = await import("../../api/anomalies");
  const { investigationService } = await import("../../api/investigations");
  (
    anomalyService.getFleetInsights as ReturnType<typeof vi.fn>
  ).mockResolvedValue(insights);
  (
    anomalyService.getRecentAnomalies as ReturnType<typeof vi.fn>
  ).mockResolvedValue(recent);
  (investigationService.list as ReturnType<typeof vi.fn>).mockResolvedValue(
    investigations,
  );
}

describe("AlertsPage (mocked)", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    await setupMocks();
  });

  it("renders the main heading", () => {
    render(<AlertsPage />);
    expect(screen.getByText("Anomaliler")).toBeInTheDocument();
  });

  it("renders the description subtitle", () => {
    render(<AlertsPage />);
    expect(
      screen.getByText(
        "Filo yakıt sapmaları, bakım ihtiyaçları ve operasyonel riskler",
      ),
    ).toBeInTheDocument();
  });

  it("renders all day-filter buttons", () => {
    render(<AlertsPage />);
    expect(screen.getByText("7 Gün")).toBeInTheDocument();
    expect(screen.getByText("14 Gün")).toBeInTheDocument();
    expect(screen.getByText("30 Gün")).toBeInTheDocument();
    expect(screen.getByText("60 Gün")).toBeInTheDocument();
    expect(screen.getByText("90 Gün")).toBeInTheDocument();
  });

  it("renders KPI card labels immediately", () => {
    render(<AlertsPage />);
    expect(screen.getByText("Yakıt Açığı")).toBeInTheDocument();
    expect(screen.getByText("Güzergah Sapması")).toBeInTheDocument();
    expect(screen.getByText("Toplam Maliyet Kaçağı")).toBeInTheDocument();
    // "Bakım Adayı" appears in both KPI label and tab — getAllByText is safe
    expect(screen.getAllByText("Bakım Adayı").length).toBeGreaterThanOrEqual(1);
  });

  it("shows dash placeholder when leakage = 0", async () => {
    await setupMocks(INSIGHTS_CLEAN);
    render(<AlertsPage />);
    // After data loads, fuel_gap_liters=0 → "—", route_deviation_km=0 → "0 km",
    // total_leakage_cost=0 → "—". At least one "—" should appear.
    await waitFor(() => {
      const dashes = screen.getAllByText("—");
      expect(dashes.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows Yakıt Açığı value when leakage > 0", async () => {
    await setupMocks(INSIGHTS_ALERT, RECENT_EMPTY);
    render(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText("150 L")).toBeInTheDocument();
    });
  });

  it("shows maintenance count as urgent+warning sum", async () => {
    await setupMocks(INSIGHTS_ALERT, RECENT_EMPTY);
    render(<AlertsPage />);
    await waitFor(() => {
      // urgent(2) + warning(3) = 5 — may appear more than once in badges/counters
      expect(screen.getAllByText("5").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("renders SeverityFilter tab bar with all tabs", async () => {
    render(<AlertsPage />);
    // "Tümü" appears in both the tab bar and the status filter — use getAllByText
    await waitFor(() => {
      expect(screen.getAllByText("Tümü").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Yakıt Kaçağı")).toBeInTheDocument();
      expect(screen.getAllByText("Bakım Adayı").length).toBeGreaterThanOrEqual(
        1,
      );
      expect(screen.getByText("Soruşturmalar")).toBeInTheDocument();
    });
  });

  it("shows Yakıt Kaçağı Özeti section in all-tab", async () => {
    render(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText("Yakıt Kaçağı Özeti")).toBeInTheDocument();
    });
  });

  it('shows "Temiz" when fuel_gap_liters is 0', async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_EMPTY);
    render(<AlertsPage />);
    await waitFor(() => {
      const temizEls = screen.getAllByText("Temiz");
      expect(temizEls.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows LeakageSummary component when leakage > 0", async () => {
    await setupMocks(INSIGHTS_ALERT, RECENT_EMPTY);
    render(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("leakage-summary")).toBeInTheDocument();
    });
  });

  it("shows Bakım Adayları with maintenance table when vehicles present", async () => {
    await setupMocks(INSIGHTS_ALERT, RECENT_EMPTY);
    render(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText("Bakım Adayları")).toBeInTheDocument();
      expect(screen.getByTestId("maintenance-table")).toBeInTheDocument();
    });
  });

  it("shows urgent count badge", async () => {
    await setupMocks(INSIGHTS_ALERT, RECENT_EMPTY);
    render(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText("2 Acil")).toBeInTheDocument();
    });
  });

  it("shows warning count badge", async () => {
    await setupMocks(INSIGHTS_ALERT, RECENT_EMPTY);
    render(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText("3 Uyarı")).toBeInTheDocument();
    });
  });

  it("renders Son Anomali Kayıtları section in all-tab", async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_DATA);
    render(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText("Son Anomali Kayıtları")).toBeInTheDocument();
    });
  });

  it("renders anomaly plate", async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_DATA);
    render(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText("34XYZ99")).toBeInTheDocument();
    });
  });

  it("renders anomaly driver name", async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_DATA);
    render(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText("— Ahmet Yılmaz")).toBeInTheDocument();
    });
  });

  it("renders anomaly description text", async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_DATA);
    render(<AlertsPage />);
    await waitFor(() => {
      expect(
        screen.getByText("Yakıt tüketimi beklenenin üzerinde"),
      ).toBeInTheDocument();
    });
  });

  it("shows total record count", async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_DATA);
    render(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText("2 kayıt")).toBeInTheDocument();
    });
  });

  it("renders status filter buttons", async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_DATA);
    render(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText("Açık")).toBeInTheDocument();
      // "Onaylı" appears in both filter button and anomaly badge — use getAllByText
      expect(screen.getAllByText("Onaylı").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Çözüldü")).toBeInTheDocument();
    });
  });

  it("renders anomali tipi select with correct options", async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_DATA);
    render(<AlertsPage />);
    await waitFor(() => {
      const select = screen.getByRole("combobox", {
        name: "Anomali tipi",
      }) as HTMLSelectElement;
      expect(select.options.length).toBe(4);
    });
  });

  it("shows no-match message when anomalies array is empty", async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_EMPTY);
    render(<AlertsPage />);
    await waitFor(() => {
      expect(
        screen.getByText("Bu filtreyle eşleşen anomali yok."),
      ).toBeInTheDocument();
    });
  });

  it("shows Onaylı badge for acknowledged anomaly", async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_DATA);
    render(<AlertsPage />);
    // anomaly id=2 has acknowledged_at set — badge + filter button both say Onaylı
    await waitFor(() => {
      expect(screen.getAllByText("Onaylı").length).toBeGreaterThanOrEqual(2);
    });
  });

  it("shows Onayla button for open anomaly", async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_DATA);
    render(<AlertsPage />);
    await waitFor(() => {
      const onaylaBtns = screen.getAllByText("Onayla");
      expect(onaylaBtns.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows Çöz button for open/acknowledged anomaly", async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_DATA);
    render(<AlertsPage />);
    await waitFor(() => {
      const cozBtns = screen.getAllByText("Çöz");
      expect(cozBtns.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("opens resolve modal when Çöz button is clicked", async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_DATA);
    render(<AlertsPage />);
    await waitFor(() => screen.getAllByText("Çöz"));
    const cozBtns = screen.getAllByText("Çöz");
    fireEvent.click(cozBtns[0]);
    await waitFor(() => {
      expect(screen.getByText("Anomaliyi Çöz")).toBeInTheDocument();
    });
  });

  it("resolve modal shows textarea with correct placeholder", async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_DATA);
    render(<AlertsPage />);
    await waitFor(() => screen.getAllByText("Çöz"));
    fireEvent.click(screen.getAllByText("Çöz")[0]);
    await waitFor(() => {
      expect(
        screen.getByPlaceholderText(
          "Ne yapıldı? Sahte alarm mı, gerçek bulgu mu?",
        ),
      ).toBeInTheDocument();
    });
  });

  it("resolve modal closes when İptal is clicked", async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_DATA);
    render(<AlertsPage />);
    await waitFor(() => screen.getAllByText("Çöz"));
    fireEvent.click(screen.getAllByText("Çöz")[0]);
    await waitFor(() => screen.getByText("İptal"));
    fireEvent.click(screen.getByText("İptal"));
    await waitFor(() => {
      expect(screen.queryByText("Anomaliyi Çöz")).not.toBeInTheDocument();
    });
  });

  it("resolve modal closes when X button is clicked", async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_DATA);
    render(<AlertsPage />);
    await waitFor(() => screen.getAllByText("Çöz"));
    fireEvent.click(screen.getAllByText("Çöz")[0]);
    await waitFor(() => screen.getByLabelText("Kapat"));
    fireEvent.click(screen.getByLabelText("Kapat"));
    await waitFor(() => {
      expect(screen.queryByText("Anomaliyi Çöz")).not.toBeInTheDocument();
    });
  });

  it("Soruşturmalar tab shows kanban and pattern list", async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_EMPTY);
    render(<AlertsPage />);
    await waitFor(() => screen.getByText("Soruşturmalar"));
    fireEvent.click(screen.getByText("Soruşturmalar"));
    await waitFor(() => {
      expect(screen.getByTestId("investigations-kanban")).toBeInTheDocument();
      expect(screen.getByTestId("pattern-list")).toBeInTheDocument();
    });
  });

  it("Bakım Adayı tab hides leakage section", async () => {
    await setupMocks(INSIGHTS_ALERT, RECENT_EMPTY);
    render(<AlertsPage />);
    // "Bakım Adayı" appears in KPI label AND tab button — click the tab button
    await waitFor(() => screen.getAllByText("Bakım Adayı"));
    const bakimAdayiEls = screen.getAllByText("Bakım Adayı");
    // Tab button is a <button> element
    const tabBtn = bakimAdayiEls.find(
      (el) => el.tagName === "BUTTON" || el.closest("button"),
    );
    fireEvent.click(tabBtn!.closest("button") ?? tabBtn!);
    await waitFor(() => {
      expect(screen.getByText("Bakım Adayları")).toBeInTheDocument();
      expect(screen.queryByText("Yakıt Kaçağı Özeti")).not.toBeInTheDocument();
    });
  });

  it("Yakıt Kaçağı tab hides maintenance section", async () => {
    await setupMocks(INSIGHTS_ALERT, RECENT_EMPTY);
    render(<AlertsPage />);
    await waitFor(() => screen.getByText("Yakıt Kaçağı"));
    fireEvent.click(screen.getByText("Yakıt Kaçağı"));
    await waitFor(() => {
      expect(screen.getByText("Yakıt Kaçağı Özeti")).toBeInTheDocument();
      expect(screen.queryByText("Bakım Adayları")).not.toBeInTheDocument();
    });
  });

  it("RCA summary is displayed when present", async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_DATA);
    render(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText("Uzun güzergah")).toBeInTheDocument();
    });
  });

  it("suggested action is displayed when present", async () => {
    await setupMocks(INSIGHTS_CLEAN, RECENT_DATA);
    render(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText("→ Güzergahı optimize edin")).toBeInTheDocument();
    });
  });
});
