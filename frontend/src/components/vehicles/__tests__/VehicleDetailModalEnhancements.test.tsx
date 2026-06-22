/**
 * VehicleDetailModal geliştirme testi
 * - Stat kartları: toplam_sefer, toplam_km, ort_tuketim, toplam_yakit
 * - Verimlilik skoru: hedef altında vs üstünde
 * - Olay zaman çizelgesi
 * - Muayene tarihi badge'i
 */
import { render, screen, waitFor } from "../../../test/test-utils";
import { describe, it, expect, vi } from "vitest";
import { VehicleDetailModal } from "../VehicleDetailModal";
import { Vehicle } from "../../../types";

vi.mock("../../../api/vehicles", () => ({
  vehicleService: {
    getStats: vi.fn().mockResolvedValue({
      arac_id: 1,
      plaka: "34ABC123",
      toplam_sefer: 42,
      toplam_km: 75000,
      ort_tuketim: 28.5,
      toplam_yakit: 21375,
      en_iyi_tuketim: 25.1,
      en_kotu_tuketim: 35.8,
    }),
    getEvents: vi.fn().mockResolvedValue([
      {
        id: 1,
        event_type: "STATUS_CHANGE",
        old_status: "Planlandı",
        new_status: "Tamamlandı",
        triggered_by: "driver",
        details: null,
        created_at: "2026-01-10T10:00:00Z",
      },
    ]),
  },
}));

const baseVehicle: Vehicle = {
  id: 1,
  plaka: "34ABC123",
  marka: "Mercedes",
  model: "Actros",
  yil: 2020,
  yakit_tipi: "Dizel",
  hedef_tuketim: 30,
  aktif: true,
};

describe("VehicleDetailModal — Stat Kartları", () => {
  it("toplam_sefer değerini gösterir", async () => {
    render(
      <VehicleDetailModal isOpen onClose={vi.fn()} vehicle={baseVehicle} />,
    );
    await waitFor(() => expect(screen.getByText("42")).toBeInTheDocument());
  });

  it("toplam_km türkçe formatla gösterir", async () => {
    render(
      <VehicleDetailModal isOpen onClose={vi.fn()} vehicle={baseVehicle} />,
    );
    await waitFor(() =>
      expect(screen.getByText(/75\.000 km/)).toBeInTheDocument(),
    );
  });

  it("ort_tuketim L/100km formatında gösterir", async () => {
    render(
      <VehicleDetailModal isOpen onClose={vi.fn()} vehicle={baseVehicle} />,
    );
    // Stat kartı + verimlilik bölümü aynı değeri gösterir → getAllByText kullan
    await waitFor(() =>
      expect(screen.getAllByText(/28\.5 L\/100km/)[0]).toBeInTheDocument(),
    );
  });

  it("toplam_yakit L formatında gösterir", async () => {
    render(
      <VehicleDetailModal isOpen onClose={vi.fn()} vehicle={baseVehicle} />,
    );
    await waitFor(() =>
      expect(screen.getByText(/21\.375 L/)).toBeInTheDocument(),
    );
  });
});

describe("VehicleDetailModal — Verimlilik Skoru", () => {
  it('ort_tuketim hedef_tuketime göre daha iyi ise "verimli" gösterir', async () => {
    // hedef_tuketim: 30, ort_tuketim: 28.5 → %5 verimli
    render(
      <VehicleDetailModal isOpen onClose={vi.fn()} vehicle={baseVehicle} />,
    );
    // "+%5.0 verimli" — spesifik regex kullan, "Verimlilik Skoru" etiketi ile çakışmasın
    await waitFor(() =>
      expect(screen.getByText(/\+%5\.0 verimli/)).toBeInTheDocument(),
    );
  });

  it('ort_tuketim hedef_tuketime göre kötü ise "kayıp" gösterir', async () => {
    const { vehicleService } = await import("../../../api/vehicles");
    vi.mocked(vehicleService.getStats).mockResolvedValueOnce({
      arac_id: 1,
      plaka: "34ABC123",
      toplam_sefer: 10,
      toplam_km: 10000,
      ort_tuketim: 35, // 30 hedef, 35 gerçek → %16.7 kayıp
      toplam_yakit: 3500,
    });
    render(
      <VehicleDetailModal isOpen onClose={vi.fn()} vehicle={baseVehicle} />,
    );
    // "-%16.7 kayıp" formatı — spesifik regex
    await waitFor(() =>
      expect(screen.getByText(/-%\d+\.\d+ kayıp/)).toBeInTheDocument(),
    );
  });
});

describe("VehicleDetailModal — Araç Bilgileri", () => {
  it("plaka ve marka / model gösterir", () => {
    render(
      <VehicleDetailModal isOpen onClose={vi.fn()} vehicle={baseVehicle} />,
    );
    expect(screen.getByText("34ABC123")).toBeInTheDocument();
    expect(screen.getByText(/Mercedes/)).toBeInTheDocument();
    expect(screen.getByText(/Actros/)).toBeInTheDocument();
  });

  it("modal kapalıyken hiçbir şey render etmez", () => {
    const { container } = render(
      <VehicleDetailModal
        isOpen={false}
        onClose={vi.fn()}
        vehicle={baseVehicle}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("vehicle null ise hiçbir şey render etmez", () => {
    const { container } = render(
      <VehicleDetailModal isOpen onClose={vi.fn()} vehicle={null} />,
    );
    expect(container.firstChild).toBeNull();
  });
});

describe("VehicleDetailModal — Muayene Tarihi", () => {
  it("muayene tarihi geçmişse tehlike rozeti gösterir", async () => {
    const vehicle: Vehicle = { ...baseVehicle, muayene_tarihi: "2020-01-01" };
    render(<VehicleDetailModal isOpen onClose={vi.fn()} vehicle={vehicle} />);
    // vehicleDetailText.inspection.expiredBadge = 'MUAYENESİ GEÇMİŞ'
    await waitFor(() =>
      expect(screen.getByText("MUAYENESİ GEÇMİŞ")).toBeInTheDocument(),
    );
  });

  it("muayene tarihi 30 gün içinde ise uyarı rozeti gösterir", async () => {
    const soon = new Date(Date.now() + 10 * 86400000)
      .toISOString()
      .split("T")[0];
    const vehicle: Vehicle = { ...baseVehicle, muayene_tarihi: soon };
    render(<VehicleDetailModal isOpen onClose={vi.fn()} vehicle={vehicle} />);
    // vehicleDetailText.inspection.expiringSoonBadge(days) = `${days} GÜN KALDI`
    // Türkçe büyük harf: "GÜN KALDI" (regular I, Ü) — /i flag eşleşmez, kesin regex kullan
    await waitFor(() =>
      expect(screen.getByText(/\d+ GÜN KALDI/)).toBeInTheDocument(),
    );
  });
});
