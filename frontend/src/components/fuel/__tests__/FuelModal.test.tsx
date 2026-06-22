import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import { FuelModal } from "../FuelModal";
import { fuelModalText } from "../../../resources/tr/fuel";

// Mock vehicleService used inside FuelModal via React Query
vi.mock("../../../api/vehicles", () => ({
  vehicleService: {
    getAll: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
}));

const defaultProps = {
  isOpen: true,
  onClose: vi.fn(),
  onSave: vi.fn().mockResolvedValue(undefined),
  record: null,
};

describe("FuelModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultProps.onClose = vi.fn();
    defaultProps.onSave = vi.fn().mockResolvedValue(undefined);
  });

  it("renders nothing when isOpen=false", () => {
    render(<FuelModal {...defaultProps} isOpen={false} />);
    // Modal uses portal — when not open it returns null
    expect(
      screen.queryByText(fuelModalText.createTitle),
    ).not.toBeInTheDocument();
  });

  it("shows create title when no record is given", async () => {
    render(<FuelModal {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByText(fuelModalText.createTitle)).toBeInTheDocument();
    });
  });

  it("shows edit title when a record is provided", async () => {
    const record: any = {
      id: 1,
      tarih: "2024-01-15T00:00:00",
      arac_id: 2,
      istasyon: "BP Ankara",
      litre: 300,
      fiyat_tl: 35,
      birim_fiyat: 35,
      toplam_tutar: 10500,
      km_sayac: 120000,
      depo_durumu: fuelModalText.enums.full,
      durum: fuelModalText.enums.pending,
    };
    render(<FuelModal {...defaultProps} record={record} />);
    await waitFor(() => {
      expect(screen.getByText(fuelModalText.editTitle)).toBeInTheDocument();
    });
  });

  it("renders all main field labels", async () => {
    render(<FuelModal {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByText(fuelModalText.labels.date)).toBeInTheDocument();
    });
    expect(screen.getByText(fuelModalText.labels.vehicle)).toBeInTheDocument();
    expect(screen.getByText(fuelModalText.labels.station)).toBeInTheDocument();
    expect(screen.getByText(fuelModalText.labels.liters)).toBeInTheDocument();
    expect(screen.getByText(fuelModalText.labels.total)).toBeInTheDocument();
    expect(
      screen.getByText(fuelModalText.labels.tankStatus),
    ).toBeInTheDocument();
  });

  it("renders cancel and save buttons", async () => {
    render(<FuelModal {...defaultProps} />);
    await waitFor(() => {
      expect(
        screen.getByText(fuelModalText.actions.cancel),
      ).toBeInTheDocument();
    });
    expect(screen.getByText(fuelModalText.actions.save)).toBeInTheDocument();
  });

  it("calls onClose when cancel button is clicked", async () => {
    render(<FuelModal {...defaultProps} />);
    await waitFor(() => {
      expect(
        screen.getByText(fuelModalText.actions.cancel),
      ).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(fuelModalText.actions.cancel));
    expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
  });

  it("shows station placeholder text", async () => {
    render(<FuelModal {...defaultProps} />);
    await waitFor(() => {
      expect(
        screen.getByPlaceholderText(fuelModalText.placeholders.station),
      ).toBeInTheDocument();
    });
  });

  it("shows validation error when submitting empty station", async () => {
    render(<FuelModal {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByText(fuelModalText.actions.save)).toBeInTheDocument();
    });
    // Click save without filling required station
    fireEvent.click(screen.getByText(fuelModalText.actions.save));
    await waitFor(() => {
      expect(
        screen.getByText(fuelModalText.validation.stationRequired),
      ).toBeInTheDocument();
    });
  });

  it("renders vehicle select dropdown with placeholder", async () => {
    render(<FuelModal {...defaultProps} />);
    await waitFor(() => {
      expect(
        screen.getByText(fuelModalText.placeholders.vehicle),
      ).toBeInTheDocument();
    });
  });

  it("renders description text", async () => {
    render(<FuelModal {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByText(fuelModalText.description)).toBeInTheDocument();
    });
  });
});
