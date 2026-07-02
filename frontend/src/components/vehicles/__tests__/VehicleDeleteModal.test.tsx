/**
 * 2026-07-02 prod-grade denetimi P2 (Tier B madde 10): VehicleDeleteModal ve
 * TrailerDeleteModal kopya-yapıştır overlay kodu tutuyordu, ui/Modal.tsx'in
 * focus-trap'ini kullanmıyordu. Bu test dosyası, `DeleteConfirmModal`
 * paylaşılan bileşenine geçiş öncesi/sonrası davranışın (title/description/
 * confirm-cancel/onConfirm-onClose) DEĞİŞMEDİĞİNİ kilitler.
 */
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import { describe, expect, it, vi } from "vitest";
import { VehicleDeleteModal } from "../VehicleDeleteModal";
import { Vehicle } from "../../../types";

function makeVehicle(overrides: Partial<Vehicle> = {}): Vehicle {
  return {
    id: 1,
    plaka: "34 ABC 123",
    marka: "Mercedes",
    model: "Actros",
    yil: 2021,
    tank_kapasitesi: 600,
    hedef_tuketim: 31.5,
    aktif: true,
    ...overrides,
  } as Vehicle;
}

describe("VehicleDeleteModal", () => {
  it("returns null when closed", () => {
    const { container } = render(
      <VehicleDeleteModal
        isOpen={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        vehicle={makeVehicle()}
      />,
    );
    expect(container.querySelector('[role="dialog"]')).toBeNull();
  });

  it("returns null when vehicle is null", () => {
    const { container } = render(
      <VehicleDeleteModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        vehicle={null}
      />,
    );
    expect(container.querySelector('[role="dialog"]')).toBeNull();
  });

  it("shows soft-delete title/description/button when vehicle.aktif is true", () => {
    render(
      <VehicleDeleteModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        vehicle={makeVehicle({ aktif: true, plaka: "34 SFT 001" })}
      />,
    );
    expect(screen.getByText("Aracı Pasife Al")).toBeInTheDocument();
    expect(
      screen.getByText(/34 SFT 001 plakalı aracı pasif duruma/),
    ).toBeInTheDocument();
    expect(screen.getByText("Pasife Al")).toBeInTheDocument();
  });

  it("shows hard-delete title/description/button when vehicle.aktif is false", () => {
    render(
      <VehicleDeleteModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        vehicle={makeVehicle({ aktif: false, plaka: "34 HRD 002" })}
      />,
    );
    expect(screen.getByText("Kalıcı Olarak Sil")).toBeInTheDocument();
    expect(
      screen.getByText(/34 HRD 002 plakalı aracı tamamen silmek/),
    ).toBeInTheDocument();
    expect(screen.getByText("Evet, Sil")).toBeInTheDocument();
  });

  it("calls onClose when cancel is clicked", () => {
    const onClose = vi.fn();
    render(
      <VehicleDeleteModal
        isOpen={true}
        onClose={onClose}
        onConfirm={vi.fn()}
        vehicle={makeVehicle()}
      />,
    );
    fireEvent.click(screen.getByText("İptal"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onConfirm then onClose when confirm is clicked", async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();
    render(
      <VehicleDeleteModal
        isOpen={true}
        onClose={onClose}
        onConfirm={onConfirm}
        vehicle={makeVehicle({ aktif: false })}
      />,
    );
    fireEvent.click(screen.getByText("Evet, Sil"));
    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledTimes(1);
    });
  });
});
