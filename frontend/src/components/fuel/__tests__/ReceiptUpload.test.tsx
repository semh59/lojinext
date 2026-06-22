import { describe, expect, it, vi } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { render } from "../../../test/test-utils";

vi.mock("../../../api/fuel", () => ({
  fuelService: {
    ocrPreview: vi.fn().mockResolvedValue({
      ham_metin: "PO 45.5 LT",
      yapilandirilmis: {
        litre: 45.5,
        tutar: 1234.56,
        km: 123456,
        tarih: "01/06/2026",
        istasyon: "PETROL OFISI",
      },
    }),
  },
}));

describe("ReceiptUpload", () => {
  it("uploads a file and shows OCR parsed preview", async () => {
    const { ReceiptUpload } = await import("../ReceiptUpload");
    render(<ReceiptUpload onConfirm={vi.fn()} />);
    const file = new File([new Uint8Array([0xff, 0xd8, 0xff])], "fis.jpg", {
      type: "image/jpeg",
    });
    const input = screen.getByLabelText(/fiş fotoğrafı/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    expect(await screen.findByDisplayValue("45.5")).toBeInTheDocument();
    expect(await screen.findByDisplayValue("PETROL OFISI")).toBeInTheDocument();
  });

  it("calls onConfirm with the (possibly edited) fields", async () => {
    const onConfirm = vi.fn();
    const { ReceiptUpload } = await import("../ReceiptUpload");
    render(<ReceiptUpload onConfirm={onConfirm} />);
    const file = new File([new Uint8Array([0xff, 0xd8, 0xff])], "fis.jpg", {
      type: "image/jpeg",
    });
    fireEvent.change(screen.getByLabelText(/fiş fotoğrafı/i), {
      target: { files: [file] },
    });
    const btn = await screen.findByText("Onayla ve kaydet");
    fireEvent.click(btn);
    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({ istasyon: "PETROL OFISI", litre: 45.5 }),
    );
  });
});
