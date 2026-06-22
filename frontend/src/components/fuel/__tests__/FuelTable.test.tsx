import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "../../../test/test-utils";

import { FuelRecord } from "../../../types";
import { FuelTable } from "../FuelTable";

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: (args: { count?: number }) => {
    const count = args?.count ?? 0;
    return {
      getTotalSize: () => count * 80,
      getVirtualItems: () =>
        Array.from({ length: count }).map((_, index) => ({
          key: `row-${index}`,
          index,
          size: 80,
          start: index * 80,
        })),
    };
  },
}));

const mockRecords: FuelRecord[] = [
  {
    id: 1,
    tarih: "2026-01-25",
    arac_id: 1,
    plaka: "34ABC123",
    istasyon: "Shell Maslak",
    litre: 450,
    birim_fiyat: 42.5,
    toplam_tutar: 19125,
    km_sayac: 45000,
    depo_durumu: "Doldu",
    durum: "Bekliyor",
  },
];

describe("FuelTable", () => {
  it("renders loading state", () => {
    render(
      <FuelTable
        records={[]}
        loading={true}
        onEdit={() => {}}
        onDelete={() => {}}
      />,
    );
    const pulses = screen
      .getAllByRole("generic")
      .filter((element) => element.className.includes("animate-pulse"));
    expect(pulses.length).toBeGreaterThan(0);
  });

  it("renders empty state", () => {
    render(
      <FuelTable
        records={[]}
        loading={false}
        onEdit={() => {}}
        onDelete={() => {}}
      />,
    );
    expect(screen.getByText(/Kayıt Bulunamadı/i)).toBeInTheDocument();
  });

  it("renders records correctly", () => {
    render(
      <FuelTable
        records={mockRecords}
        loading={false}
        onEdit={() => {}}
        onDelete={() => {}}
      />,
    );
    expect(screen.getByText("34ABC123")).toBeInTheDocument();
    expect(screen.getByText("Shell Maslak")).toBeInTheDocument();
    expect(screen.getByText("450.0 L")).toBeInTheDocument();
  });

  it("calls onEdit when edit button clicked", () => {
    const handleEdit = vi.fn();
    render(
      <FuelTable
        records={mockRecords}
        loading={false}
        onEdit={handleEdit}
        onDelete={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Düzenle/i }));

    expect(handleEdit).toHaveBeenCalledTimes(1);
    expect(handleEdit).toHaveBeenCalledWith(mockRecords[0]);
  });

  it("calls onDelete when delete button clicked", () => {
    const handleDelete = vi.fn();
    render(
      <FuelTable
        records={mockRecords}
        loading={false}
        onEdit={() => {}}
        onDelete={handleDelete}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Sil/i }));

    expect(handleDelete).toHaveBeenCalledTimes(1);
    expect(handleDelete).toHaveBeenCalledWith(mockRecords[0]);
  });
});
