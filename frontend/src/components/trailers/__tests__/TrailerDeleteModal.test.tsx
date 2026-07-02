/**
 * 2026-07-02 prod-grade denetimi P2 (Tier B madde 10): bkz.
 * VehicleDeleteModal.test.tsx başlık yorumu — aynı gerekçe.
 */
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import { describe, expect, it, vi } from "vitest";
import TrailerDeleteModal from "../TrailerDeleteModal";
import { Dorse } from "../../../types";

function makeTrailer(overrides: Partial<Dorse> = {}): Dorse {
  return {
    id: 1,
    plaka: "34 TRL 456",
    tipi: "Tenteli",
    bos_agirlik_kg: 7000,
    maks_yuk_kapasitesi_kg: 27000,
    lastik_sayisi: 6,
    aktif: true,
    ...overrides,
  } as Dorse;
}

describe("TrailerDeleteModal", () => {
  it("returns null when trailer is null", () => {
    const { container } = render(
      <TrailerDeleteModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        trailer={null}
      />,
    );
    expect(container.querySelector('[role="dialog"]')).toBeNull();
  });

  it("returns null when closed", () => {
    const { container } = render(
      <TrailerDeleteModal
        isOpen={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        trailer={makeTrailer()}
      />,
    );
    expect(container.querySelector('[role="dialog"]')).toBeNull();
  });

  it("shows title/description/confirm/cancel text", () => {
    render(
      <TrailerDeleteModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        trailer={makeTrailer({ plaka: "34 TRL 999" })}
      />,
    );
    expect(screen.getByText("Dorse Silinsin mi?")).toBeInTheDocument();
    expect(
      screen.getByText(/34 TRL 999 plakalı dorseyi silmek istediğinize/),
    ).toBeInTheDocument();
    expect(screen.getByText("Dorseyi Kalıcı Olarak Sil")).toBeInTheDocument();
    expect(screen.getByText("Vazgeç")).toBeInTheDocument();
  });

  it("calls onClose when cancel is clicked", () => {
    const onClose = vi.fn();
    render(
      <TrailerDeleteModal
        isOpen={true}
        onClose={onClose}
        onConfirm={vi.fn()}
        trailer={makeTrailer()}
      />,
    );
    fireEvent.click(screen.getByText("Vazgeç"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onConfirm when confirm is clicked", async () => {
    const onConfirm = vi.fn();
    render(
      <TrailerDeleteModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={onConfirm}
        trailer={makeTrailer()}
      />,
    );
    fireEvent.click(screen.getByText("Dorseyi Kalıcı Olarak Sil"));
    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledTimes(1);
    });
  });

  it("disables both buttons while isDeleting (shared Button's loading state)", () => {
    render(
      <TrailerDeleteModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        trailer={makeTrailer()}
        isDeleting={true}
      />,
    );
    expect(
      screen.getByText("Dorseyi Kalıcı Olarak Sil").closest("button"),
    ).toBeDisabled();
    expect(screen.getByText("Vazgeç").closest("button")).toBeDisabled();
  });
});
