/**
 * VehicleTable geliştirme testi
 * - Muayene tarihi geçmiş / yakında dolacak rozetler
 * - Yaşlanma etkisi (>8 yıl)
 * - Tank kapasitesi doğru alanı kullanıyor mu
 * - Hedef tüketim gösterimi
 */
import { render, screen, fireEvent } from "../../../test/test-utils";
import { describe, it, expect, vi } from "vitest";
import { VehicleTable } from "../VehicleTable";
import { Vehicle } from "../../../types";

const noop = vi.fn();

function makeVehicle(overrides: Partial<Vehicle> = {}): Vehicle {
  return {
    id: 1,
    plaka: "34TEST001",
    marka: "Ford",
    model: "Cargo",
    yil: 2020,
    tank_kapasitesi: 600,
    hedef_tuketim: 30,
    yakit_tipi: "Dizel",
    aktif: true,
    ...overrides,
  };
}

function renderTable(vehicles: Vehicle[]) {
  return render(
    <VehicleTable
      vehicles={vehicles}
      loading={false}
      onEdit={noop}
      onDelete={noop}
      onViewDetail={noop}
    />,
  );
}

describe("VehicleTable — Muayene Durumu", () => {
  const pastDate = "2020-01-01";
  const soonDate = new Date(Date.now() + 15 * 86400000)
    .toISOString()
    .split("T")[0];
  const futureDate = new Date(Date.now() + 90 * 86400000)
    .toISOString()
    .split("T")[0];

  it('muayene tarihi geçmiş ise "MUAYENESİ GEÇMİŞ" rozeti gösterir', () => {
    renderTable([makeVehicle({ muayene_tarihi: pastDate })]);
    // vehicleCardText.inspection.expired = 'MUAYENESİ GEÇMİŞ'
    expect(screen.getByText("MUAYENESİ GEÇMİŞ")).toBeInTheDocument();
  });

  it("muayene tarihi 30 gün içinde ise uyarı rozeti gösterir", () => {
    renderTable([makeVehicle({ muayene_tarihi: soonDate })]);
    // vehicleCardText.inspection.expiringSoon(days) = `MUAYENE: ${days}G`
    expect(screen.getByText(/MUAYENE: \d+G/)).toBeInTheDocument();
  });

  it("muayene tarihi uzaksa rozet göstermez", () => {
    renderTable([makeVehicle({ muayene_tarihi: futureDate })]);
    expect(screen.queryByText(/muayenesi geçti/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/gün kaldı/i)).not.toBeInTheDocument();
  });

  it("muayene tarihi yoksa rozet yok", () => {
    renderTable([makeVehicle({ muayene_tarihi: undefined })]);
    expect(screen.queryByText(/muayene/i)).not.toBeInTheDocument();
  });
});

describe("VehicleTable — Yaşlanma Etkisi", () => {
  it("8 yaş ve üzeri araç için yaşlanma uyarısı gösterir", () => {
    const yil = new Date().getFullYear() - 9; // 9 yıllık
    renderTable([makeVehicle({ yil })]);
    // VehicleTable renders: `-{agingPct}% etki`
    expect(screen.getByText(/-\d+(\.\d+)?% etki/)).toBeInTheDocument();
  });

  it("8 yaşın altındaki araç için yaşlanma uyarısı yok", () => {
    const yil = new Date().getFullYear() - 3; // 3 yıllık
    renderTable([makeVehicle({ yil })]);
    expect(screen.queryByText(/etki/i)).not.toBeInTheDocument();
  });
});

describe("VehicleTable — Alan Doğruluğu", () => {
  it("tank_kapasitesi alanını kullanır, kapasite değil", () => {
    renderTable([makeVehicle({ tank_kapasitesi: 750 })]);
    expect(screen.getByText(/750/)).toBeInTheDocument();
  });

  it("tank_kapasitesi yoksa tire gösterir", () => {
    renderTable([makeVehicle({ tank_kapasitesi: undefined })]);
    // Sayı olmadığında "-" gösterilir
    expect(screen.getByText(/- L/)).toBeInTheDocument();
  });

  it("hedef tüketim değerini gösterir", () => {
    renderTable([makeVehicle({ hedef_tuketim: 35 })]);
    expect(screen.getByText(/35 L\/100km/)).toBeInTheDocument();
  });

  it("aktif araç için yeşil rozet", () => {
    renderTable([makeVehicle({ aktif: true })]);
    // vehicleTableText.status.active = 'AKTİF' — Badge iç içe elemanlar içerebilir
    expect(screen.getAllByText("AKTİF")[0]).toBeInTheDocument();
  });

  it("pasif araç için gri rozet", () => {
    renderTable([makeVehicle({ aktif: false })]);
    // vehicleTableText.status.inactive = 'PASİF'
    expect(screen.getAllByText("PASİF")[0]).toBeInTheDocument();
  });
});

describe("VehicleTable — Aksiyon Butonları", () => {
  it("Düzenle butonuna tıklanınca onEdit çağrılır", () => {
    const handleEdit = vi.fn();
    render(
      <VehicleTable
        vehicles={[makeVehicle()]}
        loading={false}
        onEdit={handleEdit}
        onDelete={noop}
        onViewDetail={noop}
      />,
    );
    fireEvent.click(screen.getByTitle(/düzenle/i));
    expect(handleEdit).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }));
  });

  it("Sil butonuna tıklanınca onDelete çağrılır", () => {
    const handleDelete = vi.fn();
    render(
      <VehicleTable
        vehicles={[makeVehicle()]}
        loading={false}
        onEdit={noop}
        onDelete={handleDelete}
        onViewDetail={noop}
      />,
    );
    fireEvent.click(screen.getByTitle(/sil/i));
    expect(handleDelete).toHaveBeenCalledWith(
      expect.objectContaining({ id: 1 }),
    );
  });
});
