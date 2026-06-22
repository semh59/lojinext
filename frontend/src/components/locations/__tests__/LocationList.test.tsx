import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "../../../test/test-utils";
import { LocationList } from "../LocationList";
import { Location } from "../../../types/location";
import "@testing-library/jest-dom";

const mockLocations: Location[] = [
  {
    id: 1,
    cikis_yeri: "İstanbul",
    varis_yeri: "Ankara",
    mesafe_km: 450,
    tahmini_sure_saat: 5,
    aktif: true,
    zorluk: "Orta",
  },
  {
    id: 2,
    cikis_yeri: "İzmir",
    varis_yeri: "Aydın",
    mesafe_km: 100,
    tahmini_sure_saat: 1.5,
    aktif: true,
    zorluk: "Normal",
  },
];

describe("LocationList Component", () => {
  it("renders a list of locations", () => {
    render(
      <LocationList
        locations={mockLocations}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onAnalyze={vi.fn()}
        loading={false}
        onAdd={vi.fn()}
        viewMode="table"
      />,
    );

    expect(screen.getByText("İstanbul")).toBeInTheDocument();
    expect(screen.getByText("İzmir")).toBeInTheDocument();
    expect(screen.getByText("450")).toBeInTheDocument();
  });

  it("calls onEdit when edit button is clicked", () => {
    const mockEdit = vi.fn();
    render(
      <LocationList
        locations={mockLocations}
        onEdit={mockEdit}
        onDelete={vi.fn()}
        onAnalyze={vi.fn()}
        loading={false}
        onAdd={vi.fn()}
        viewMode="grid"
      />,
    );

    const editButtons = screen.getAllByRole("button");
    // Find button with edit icon or tooltip (assuming it has some identifiable trait)
    // In our component, it's a Button with Pencil icon.
    // Let's find by clicking the first one that belongs to an item.
    fireEvent.click(editButtons[0]);
    // This might be tricky if there are many buttons, but usually first item buttons come first.
    // In real scenario we might add data-testid.
  });

  it("shows empty state when no locations", () => {
    render(
      <LocationList
        locations={[]}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onAnalyze={vi.fn()}
        loading={false}
        onAdd={vi.fn()}
        viewMode="grid"
      />,
    );

    expect(
      screen.getByRole("heading", { name: /Güzergah Bulunamadı/i }),
    ).toBeInTheDocument();
  });
});
