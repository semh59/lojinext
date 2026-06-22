import { render, screen, fireEvent, waitFor } from "../../../test/test-utils";
import { describe, it, expect, vi } from "vitest";
import { VehicleTable } from "../VehicleTable";
import { Vehicle } from "../../../types";

const mockVehicles: Vehicle[] = [
  {
    id: 1,
    plaka: "34ABC123",
    marka: "Ford",
    model: "Cargo",
    yil: 2023,
    tank_kapasitesi: 15000,
    hedef_tuketim: 30,
    yakit_tipi: "Dizel",
    aktif: true,
  },
  {
    id: 2,
    plaka: "06XYZ789",
    marka: "Mercedes",
    model: "Actros",
    yil: 2022,
    tank_kapasitesi: 650,
    hedef_tuketim: 28,
    yakit_tipi: "Dizel",
    aktif: false,
  },
];

describe("VehicleTable", () => {
  it("renders vehicle list correctly", () => {
    render(
      <VehicleTable
        vehicles={mockVehicles}
        loading={false}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onViewDetail={vi.fn()}
      />,
    );

    expect(screen.getByText(/34ABC123/i)).toBeInTheDocument();
    expect(screen.getByText(/Ford/i)).toBeInTheDocument();
    expect(screen.getByText(/15[.,]000 L/i)).toBeInTheDocument();
    expect(screen.getByText(/AKT/i)).toBeInTheDocument();
    expect(screen.getAllByText(/PAS/i).length).toBeGreaterThan(0);
  });

  it("shows loading state", () => {
    render(
      <VehicleTable
        vehicles={[]}
        loading={true}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onViewDetail={vi.fn()}
      />,
    );
    expect(screen.queryByText(/Hen.*Ara/i)).not.toBeInTheDocument();
  });

  it("shows empty state", () => {
    render(
      <VehicleTable
        vehicles={[]}
        loading={false}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onViewDetail={vi.fn()}
      />,
    );
    expect(screen.getByText(/Hen.*Ara/i)).toBeInTheDocument();
  });

  it("calls action handlers", async () => {
    const handleEdit = vi.fn();
    const handleDelete = vi.fn();

    render(
      <VehicleTable
        vehicles={mockVehicles}
        loading={false}
        onEdit={handleEdit}
        onDelete={handleDelete}
        onViewDetail={vi.fn()}
      />,
    );

    const deleteButtons = screen.getAllByTitle("Sil");
    fireEvent.click(deleteButtons[0]);
    await waitFor(() => {
      expect(handleDelete).toHaveBeenCalledWith(mockVehicles[0]);
    });

    const editButtons = screen.getAllByTitle(/D.+zenle/i);
    fireEvent.click(editButtons[1]);
    expect(handleEdit).toHaveBeenCalledWith(mockVehicles[1]);
  });
});
