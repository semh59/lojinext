/**
 * 2026-07-01 prod-grade denetimi P2 (Dalga 4 madde 25): TripTable virtualizer
 * `getItemKey` sağlamıyordu — 15sn polling'de veri kayıp/eklenince satır
 * kimliği index'e düşüyor, yanlış satır animasyonu/scroll kayması olabiliyor.
 * Bu test, useVirtualizer'a geçilen `getItemKey`'in trip.id'ye (index'e değil)
 * bağlı, stabil bir anahtar döndürdüğünü doğrular.
 */
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../../context/AuthContext";
import { Trip } from "../../../types";
import { TripTable } from "../TripTable";

let capturedOptions: any = null;

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: (options: any) => {
    capturedOptions = options;
    const count = options?.count ?? 0;
    return {
      getTotalSize: () => count * 140,
      getVirtualItems: () =>
        Array.from({ length: count }).map((_, i) => ({
          key: options.getItemKey ? options.getItemKey(i) : i,
          index: i,
          size: 140,
          start: i * 140,
        })),
    };
  },
}));

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

const makeTrip = (id: number): Trip => ({
  id,
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
});

describe("TripTable — virtualizer getItemKey", () => {
  it("useVirtualizer'a bir getItemKey fonksiyonu veriyor", () => {
    renderTable([makeTrip(101), makeTrip(202)]);
    expect(typeof capturedOptions?.getItemKey).toBe("function");
  });

  it("getItemKey trip.id'ye bağlı, index'e değil — polling sırasında baştan bir satır silinip yeniden çekilse bile aynı sefer aynı key'i taşır", () => {
    renderTable([makeTrip(101), makeTrip(202), makeTrip(303)]);
    const keysBefore = [0, 1, 2].map((i) => capturedOptions.getItemKey(i));
    expect(keysBefore).toEqual([101, 202, 303]);

    // "Polling" simülasyonu: baştaki sefer kayboldu, aynı array yeniden
    // render ediliyor — sefer 202 artık index 0'da.
    renderTable([makeTrip(202), makeTrip(303)]);
    const keysAfter = [0, 1].map((i) => capturedOptions.getItemKey(i));
    expect(keysAfter).toEqual([202, 303]);
    // 202'nin key'i her iki render'da da AYNI (202) — index'e göre değişmedi.
    expect(keysAfter[0]).toBe(keysBefore[1]);
  });
});
