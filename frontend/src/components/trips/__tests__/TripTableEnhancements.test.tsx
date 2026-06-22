/**
 * TripTable geliştirme testi
 * - bos_sefer, is_round_trip, version rozetleri
 * - gercek_tuketim (sadece tamamlanan seferde)
 * - Süre sapma rozeti (gecikmeli / erken)
 * - Odometer tutarsızlık uyarısı
 * - onay_notu reddedildi durumunda
 * - Plaka ve sürücü cross-page linkler
 */
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../../../context/AuthContext";
import { TripTable } from "../TripTable";
import { Trip } from "../../../types";

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: (args: any) => {
    const count = args?.count ?? 0;
    return {
      getTotalSize: () => count * 160,
      getVirtualItems: () =>
        Array.from({ length: count }).map((_, i) => ({
          key: `row-${i}`,
          index: i,
          size: 160,
          start: i * 160,
        })),
    };
  },
}));

// Temel sefer nesnesi — testler üzerinde override eder
const baseTrip: Trip = {
  id: 1,
  tarih: "2026-01-15",
  saat: "08:00",
  arac_id: 1,
  sofor_id: 1,
  guzergah_id: 1,
  cikis_yeri: "İstanbul",
  varis_yeri: "Ankara",
  mesafe_km: 450,
  bos_agirlik_kg: 8000,
  dolu_agirlik_kg: 18000,
  net_kg: 10000,
  ton: 10,
  durum: "Tamamlandı",
  plaka: "34ABC123",
  sofor_adi: "Mehmet Kaya",
  bos_sefer: false,
  is_round_trip: false,
  version: 1,
};

const defaultProps = {
  isLoading: false,
  onEdit: vi.fn(),
  onDelete: vi.fn(),
  selectedIds: [],
  onToggleSelection: vi.fn(),
  onViewDetails: vi.fn(),
};

function renderTable(trips: Trip[]) {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <TripTable trips={trips} {...defaultProps} />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("TripTable — Boş Sefer ve Yuvarlak Sefer Rozetleri", () => {
  it('bos_sefer true ise "Boş Sefer" rozeti görünür', () => {
    renderTable([{ ...baseTrip, bos_sefer: true }]);
    expect(screen.getByText("Boş Sefer")).toBeInTheDocument();
  });

  it("bos_sefer false ise rozet görünmez", () => {
    renderTable([{ ...baseTrip, bos_sefer: false }]);
    expect(screen.queryByText("Boş Sefer")).not.toBeInTheDocument();
  });

  it('is_round_trip true ise "Dönüş" rozeti görünür', () => {
    renderTable([{ ...baseTrip, is_round_trip: true }]);
    expect(screen.getByText("Dönüş")).toBeInTheDocument();
  });

  it("is_round_trip false ise rozet görünmez", () => {
    renderTable([{ ...baseTrip, is_round_trip: false }]);
    expect(screen.queryByText("Dönüş")).not.toBeInTheDocument();
  });
});

describe("TripTable — Versiyon Rozeti", () => {
  it("version 2 ise v2 rozeti gösterir", () => {
    renderTable([{ ...baseTrip, version: 2 }]);
    expect(screen.getByText("v2")).toBeInTheDocument();
  });

  it("version 1 ise rozet göstermez", () => {
    renderTable([{ ...baseTrip, version: 1 }]);
    expect(screen.queryByText("v1")).not.toBeInTheDocument();
  });

  it("version null ise rozet göstermez", () => {
    renderTable([{ ...baseTrip, version: null }]);
    expect(screen.queryByText(/^v\d/)).not.toBeInTheDocument();
  });
});

describe("TripTable — Gerçek Tüketim", () => {
  it("tamamlanan sefer + gercek_tuketim varsa gösterir", () => {
    renderTable([{ ...baseTrip, durum: "Tamamlandı", gercek_tuketim: 34.5 }]);
    expect(screen.getByText(/34\.5 L\/100km/)).toBeInTheDocument();
  });

  it("planlanan sefer için gercek_tuketim göstermez", () => {
    renderTable([{ ...baseTrip, durum: "Planlandı", gercek_tuketim: 34.5 }]);
    expect(screen.queryByText(/34\.5 L\/100km/)).not.toBeInTheDocument();
  });

  it("gercek_tuketim null ise göstermez", () => {
    renderTable([{ ...baseTrip, durum: "Tamamlandı", gercek_tuketim: null }]);
    expect(screen.queryByText(/L\/100km/)).not.toBeInTheDocument();
  });
});

describe("TripTable — Süre Sapma Rozeti", () => {
  it("15+ dakika gecikme varsa gecikmeli rozeti gösterir", () => {
    renderTable([
      {
        ...baseTrip,
        duration_min: 300,
        predicted_duration_min: 240, // 60 dk fark
      },
    ]);
    expect(screen.getByText(/\+60 dk gecikmeli/)).toBeInTheDocument();
  });

  it("15+ dakika erken varsa erken rozeti gösterir", () => {
    renderTable([
      {
        ...baseTrip,
        duration_min: 200,
        predicted_duration_min: 240, // -40 dk fark
      },
    ]);
    expect(screen.getByText(/-40 dk erken/)).toBeInTheDocument();
  });

  it("15 dakikadan az sapma varsa rozet görünmez", () => {
    renderTable([
      {
        ...baseTrip,
        duration_min: 245,
        predicted_duration_min: 240, // 5 dk fark
      },
    ]);
    expect(screen.queryByText(/dk gecikmeli/)).not.toBeInTheDocument();
    expect(screen.queryByText(/dk erken/)).not.toBeInTheDocument();
  });

  it("duration_min null ise rozet görünmez", () => {
    renderTable([
      {
        ...baseTrip,
        duration_min: null,
        predicted_duration_min: 240,
      },
    ]);
    expect(screen.queryByText(/dk gecikmeli/)).not.toBeInTheDocument();
  });
});

describe("TripTable — Odometer Tutarsızlık Uyarısı", () => {
  it("km farkı 20km üstünde ise uyarı gösterir", () => {
    renderTable([
      {
        ...baseTrip,
        km_baslangic: 100000,
        km_bitis: 100500, // 500 km ölçüm, mesafe_km: 450 → fark: +50
        mesafe_km: 450,
      },
    ]);
    expect(screen.getByText(/km farkı/i)).toBeInTheDocument();
  });

  it("km farkı 20km veya altında ise uyarı göstermez", () => {
    renderTable([
      {
        ...baseTrip,
        km_baslangic: 100000,
        km_bitis: 100460, // 460 km, mesafe_km: 450 → fark: +10
        mesafe_km: 450,
      },
    ]);
    expect(screen.queryByText(/km farkı/i)).not.toBeInTheDocument();
  });

  it("km_baslangic null ise uyarı göstermez", () => {
    renderTable([
      {
        ...baseTrip,
        km_baslangic: null,
        km_bitis: 100500,
        mesafe_km: 450,
      },
    ]);
    expect(screen.queryByText(/km farkı/i)).not.toBeInTheDocument();
  });
});

describe("TripTable — Onay Notu (Red Gerekçesi)", () => {
  it("reddedilmiş sefer + onay_notu varsa gösterir", () => {
    renderTable([
      {
        ...baseTrip,
        onay_durumu: "reddedildi",
        onay_notu: "Belge eksik",
      },
    ]);
    expect(screen.getByText(/belge eksik/i)).toBeInTheDocument();
    expect(screen.getByText(/red nedeni/i)).toBeInTheDocument();
  });

  it("onaylanan sefer için red notu göstermez", () => {
    renderTable([
      {
        ...baseTrip,
        onay_durumu: "onaylandi",
        onay_notu: "Belge eksik",
      },
    ]);
    expect(screen.queryByText(/belge eksik/i)).not.toBeInTheDocument();
  });

  it("reddedilmiş ama onay_notu null ise göstermez", () => {
    renderTable([
      {
        ...baseTrip,
        onay_durumu: "reddedildi",
        onay_notu: null,
      },
    ]);
    expect(screen.queryByText(/red nedeni/i)).not.toBeInTheDocument();
  });
});

describe("TripTable — Cross-page Navigasyon Linkleri", () => {
  it("plaka FleetPage linki doğru URL içerir", () => {
    renderTable([{ ...baseTrip, plaka: "34ABC123" }]);
    const links = screen.getAllByRole("link");
    const plakaLink = links.find(
      (l) => l.getAttribute("href")?.includes("/fleet"),
    );
    expect(plakaLink).toBeDefined();
    expect(plakaLink!.getAttribute("href")).toContain("34ABC123");
  });

  it("sürücü ismi DriversPage linki doğru URL içerir", () => {
    renderTable([{ ...baseTrip, sofor_adi: "Mehmet Kaya" }]);
    const links = screen.getAllByRole("link");
    const driverLink = links.find(
      (l) => l.getAttribute("href")?.includes("/drivers"),
    );
    expect(driverLink).toBeDefined();
    expect(driverLink!.getAttribute("href")).toContain("Mehmet%20Kaya");
  });
});

describe("TripTable — Boş Durum", () => {
  it("sefer yokken başlık görünür", () => {
    renderTable([]);
    expect(
      screen.getByRole("heading", { name: /henüz sefer yok/i }),
    ).toBeInTheDocument();
  });
});
