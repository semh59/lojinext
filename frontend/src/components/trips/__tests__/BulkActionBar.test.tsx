/**
 * BulkActionBar bileşen testi
 * - Toplu Onayla butonu gösterimi ve callback
 * - selectedCount 0 iken görünmez
 * - isApproving yüklenme durumu
 */
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { BulkActionBar } from "../BulkActionBar";

// RequirePermission: izni hep ver
vi.mock("../../../components/auth/RequirePermission", () => ({
  RequirePermission: ({ children }: any) => <>{children}</>,
}));

const defaultProps = {
  selectedCount: 3,
  onClear: vi.fn(),
  onStatusUpdate: vi.fn(),
  onCancel: vi.fn(),
  onDelete: vi.fn(),
};

describe("BulkActionBar", () => {
  describe("görünürlük", () => {
    it("selectedCount 0 ise hiçbir şey render edilmez", () => {
      const { container } = render(
        <BulkActionBar {...defaultProps} selectedCount={0} />,
      );
      expect(container.firstChild).toBeNull();
    });

    it("selectedCount > 0 ise render edilir", () => {
      render(<BulkActionBar {...defaultProps} />);
      expect(screen.getByText("3")).toBeInTheDocument();
    });
  });

  describe("toplu onayla butonu", () => {
    it('onApprove verilince "Seçilileri Onayla" butonu görünür', () => {
      render(<BulkActionBar {...defaultProps} onApprove={vi.fn()} />);
      expect(
        screen.getByRole("button", { name: /seçilileri onayla/i }),
      ).toBeInTheDocument();
    });

    it("onApprove verilmezse buton görünmez", () => {
      render(<BulkActionBar {...defaultProps} />);
      expect(
        screen.queryByRole("button", { name: /seçilileri onayla/i }),
      ).not.toBeInTheDocument();
    });

    it("butona tıklayınca onApprove çağrılır", () => {
      const handleApprove = vi.fn();
      render(<BulkActionBar {...defaultProps} onApprove={handleApprove} />);
      fireEvent.click(
        screen.getByRole("button", { name: /seçilileri onayla/i }),
      );
      expect(handleApprove).toHaveBeenCalledTimes(1);
    });

    it("isApproving true iken buton devre dışı görünür", () => {
      render(
        <BulkActionBar {...defaultProps} onApprove={vi.fn()} isApproving />,
      );
      // isLoading prop'u ile Button disabled olur
      const btn = screen.getByRole("button", { name: /seçilileri onayla/i });
      expect(btn).toBeDisabled();
    });
  });

  describe("diğer butonlar", () => {
    it('"Kapat" butonu onClear çağırır', () => {
      const handleClear = vi.fn();
      render(<BulkActionBar {...defaultProps} onClear={handleClear} />);
      // X ikonlu kapat butonu
      const buttons = screen.getAllByRole("button");
      fireEvent.click(buttons[0]); // İlk buton X
      expect(handleClear).toHaveBeenCalled();
    });
  });
});
