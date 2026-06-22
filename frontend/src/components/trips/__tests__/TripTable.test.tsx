import { render, screen } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../../context/AuthContext";
import { Trip } from "../../../types";
import { TripTable } from "../TripTable";

function withAuth(ui: React.ReactElement) {
  return render(
    <MemoryRouter>
      <AuthProvider>{ui}</AuthProvider>
    </MemoryRouter>,
  );
}

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: () => ({
    getTotalSize: () => 280,
    getVirtualItems: () => [
      { key: "row-0", index: 0, size: 140, start: 0 },
      { key: "row-1", index: 1, size: 140, start: 140 },
    ],
  }),
}));

describe("TripTable", () => {
  const mockTrips: Trip[] = [
    {
      id: 1,
      tarih: "2024-05-20",
      saat: "10:00",
      sefer_no: "SN-001",
      arac_id: 1,
      guzergah_id: 1,
      plaka: "34ABC123",
      sofor_id: 1,
      sofor_adi: "Ahmet Yılmaz",
      cikis_yeri: "Istanbul",
      varis_yeri: "Ankara",
      mesafe_km: 450,
      net_kg: 20000,
      ton: 20,
      bos_agirlik_kg: 8000,
      dolu_agirlik_kg: 28000,
      durum: "Tamamlandı",
      bos_sefer: false,
      flat_distance_km: 400,
    },
    {
      id: 2,
      tarih: "2024-05-21",
      saat: "11:00",
      sefer_no: "",
      arac_id: 1,
      guzergah_id: 2,
      plaka: "34DEF456",
      sofor_id: 2,
      sofor_adi: "Mehmet Demir",
      cikis_yeri: "Bursa",
      varis_yeri: "Izmir",
      mesafe_km: 330,
      net_kg: 15000,
      ton: 15,
      bos_agirlik_kg: 8000,
      dolu_agirlik_kg: 23000,
      durum: "Planlandı",
      bos_sefer: false,
      flat_distance_km: 300,
    },
  ];

  const defaultProps = {
    trips: mockTrips,
    isLoading: false,
    onEdit: vi.fn(),
    onDelete: vi.fn(),
    selectedIds: [],
    onToggleSelection: vi.fn(),
    onViewDetails: vi.fn(),
  };

  it("renders trip data with virtualized rows", () => {
    withAuth(<TripTable {...defaultProps} />);

    expect(screen.getByText("SN-001")).toBeInTheDocument();
    expect(screen.getByText(/Istanbul/i)).toBeInTheDocument();
    expect(screen.getByText(/Ankara/i)).toBeInTheDocument();
  });

  it("renders loading state", () => {
    withAuth(<TripTable {...defaultProps} isLoading />);
    expect(document.querySelectorAll(".animate-pulse").length).toBeGreaterThan(
      0,
    );
  });
});
