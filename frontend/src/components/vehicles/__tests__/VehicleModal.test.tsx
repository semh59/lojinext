import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import { VehicleModal } from "../VehicleModal";
import { vehicleModalText } from "../../../resources/tr/vehicles";
import { Vehicle } from "../../../types";

// Mock framer-motion
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, onClick, ...props }: any) => (
      <div onClick={onClick} {...props}>
        {children}
      </div>
    ),
  },
}));

const mockOnClose = vi.fn();
const mockOnSave = vi.fn().mockResolvedValue(undefined);

const MOCK_VEHICLE: Vehicle = {
  id: 1,
  plaka: "34ABC123",
  marka: "Mercedes",
  model: "Actros",
  yil: 2022,
  tank_kapasitesi: 800,
  hedef_tuketim: 32,
  aktif: true,
  yakit_tipi: "DIZEL",
  notlar: "Filo baş aracı",
};

describe("VehicleModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when isOpen=false", () => {
    const { container } = render(
      <VehicleModal
        isOpen={false}
        onClose={mockOnClose}
        onSave={mockOnSave}
        vehicle={null}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders create title when no vehicle provided", () => {
    render(
      <VehicleModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        vehicle={null}
      />,
    );
    expect(screen.getByText(vehicleModalText.title.create)).toBeInTheDocument();
  });

  it("renders edit title when vehicle is provided", () => {
    render(
      <VehicleModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        vehicle={MOCK_VEHICLE}
      />,
    );
    expect(screen.getByText(vehicleModalText.title.edit)).toBeInTheDocument();
  });

  it("renders form fields for create mode", () => {
    render(
      <VehicleModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        vehicle={null}
      />,
    );
    expect(
      screen.getByPlaceholderText(vehicleModalText.placeholders.plate),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(vehicleModalText.placeholders.brand),
    ).toBeInTheDocument();
  });

  it("pre-fills form with vehicle data in edit mode", () => {
    render(
      <VehicleModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        vehicle={MOCK_VEHICLE}
      />,
    );
    expect(screen.getByDisplayValue("34ABC123")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Mercedes")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Actros")).toBeInTheDocument();
  });

  it("renders active vehicle checkbox", () => {
    render(
      <VehicleModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        vehicle={null}
      />,
    );
    expect(
      screen.getByText(vehicleModalText.fields.active),
    ).toBeInTheDocument();
  });

  it("cancel button calls onClose", () => {
    render(
      <VehicleModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        vehicle={null}
      />,
    );
    const cancelBtn = screen.getByText(vehicleModalText.actions.cancel);
    fireEvent.click(cancelBtn);
    expect(mockOnClose).toHaveBeenCalled();
  });

  it("shows validation error when plate is empty on submit", async () => {
    render(
      <VehicleModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        vehicle={null}
      />,
    );
    // Click the create/submit button without filling required fields
    const submitBtn = screen.getByText(vehicleModalText.actions.create);
    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(
        screen.getByText(vehicleModalText.validation.plateMin),
      ).toBeInTheDocument();
    });
  });

  it("physics accordion toggles advanced fields", async () => {
    render(
      <VehicleModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        vehicle={null}
      />,
    );
    // Initially collapsed
    expect(
      screen.queryByText(vehicleModalText.fields.emptyWeight),
    ).not.toBeInTheDocument();

    // Click to expand
    const physicsToggle = screen.getByText(vehicleModalText.fields.physics);
    fireEvent.click(physicsToggle);

    await waitFor(() => {
      expect(
        screen.getByText(vehicleModalText.fields.emptyWeight),
      ).toBeInTheDocument();
    });
  });

  it("shows Güncelle button in edit mode", () => {
    render(
      <VehicleModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        vehicle={MOCK_VEHICLE}
      />,
    );
    expect(
      screen.getByText(vehicleModalText.actions.update),
    ).toBeInTheDocument();
  });

  it("submits with valid data and calls onSave", async () => {
    render(
      <VehicleModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        vehicle={MOCK_VEHICLE}
      />,
    );
    fireEvent.click(screen.getByText(vehicleModalText.actions.update));
    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalled();
    });
  });
});
