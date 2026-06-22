/**
 * TripFilters bileşen testi
 * - "Bugün" butonu doğru tarih aralığı setiyor mu
 * - Son güncelleme göstergesi
 * - Arama kutusu davranışı
 */
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { TripFilters } from "../TripFilters";

const mockSetFilters = vi.fn();
const mockResetFilters = vi.fn();

vi.mock("../../../stores/use-trip-store", () => ({
  useTripStore: () => ({
    filters: {
      durum: "",
      search: "",
      baslangic_tarih: "",
      bitis_tarih: "",
      onay_durumu: undefined,
      arac_id: undefined,
      sofor_id: undefined,
    },
    setFilters: mockSetFilters,
    resetFilters: mockResetFilters,
  }),
}));

vi.mock("../../../api/preferences", () => ({
  preferenceService: {
    getPreferences: vi.fn().mockResolvedValue([]),
    savePreference: vi.fn(),
    deletePreference: vi.fn(),
  },
}));

vi.mock("../../../components/shared/DataExportImport", () => ({
  DataExportImport: () => <div data-testid="export-import" />,
}));

const defaultProps = {
  onExport: vi.fn().mockResolvedValue(undefined),
  onImport: vi.fn().mockResolvedValue(undefined),
  onDownloadTemplate: vi.fn().mockResolvedValue(undefined),
};

beforeEach(() => {
  mockSetFilters.mockClear();
});

describe("TripFilters", () => {
  describe('"Bugün" hızlı filtre butonu', () => {
    it("Bugün butonunu render eder", () => {
      render(<TripFilters {...defaultProps} />);
      expect(
        screen.getByRole("button", { name: /bugün/i }),
      ).toBeInTheDocument();
    });

    it("Bugün butonuna tıklayınca bugünün tarihi set edilir", () => {
      render(<TripFilters {...defaultProps} />);
      const today = new Date().toISOString().split("T")[0];
      fireEvent.click(screen.getByRole("button", { name: /bugün/i }));
      expect(mockSetFilters).toHaveBeenCalledWith({
        baslangic_tarih: today,
        bitis_tarih: today,
      });
    });
  });

  describe("son güncelleme göstergesi", () => {
    it("dataUpdatedAt yoksa gösterge görünmez", () => {
      render(<TripFilters {...defaultProps} />);
      expect(screen.queryByText(/son güncelleme/i)).not.toBeInTheDocument();
    });

    it('dataUpdatedAt verilince "son güncelleme" gösterir', () => {
      const now = Date.now();
      render(<TripFilters {...defaultProps} dataUpdatedAt={now} />);
      expect(screen.getByText(/son güncelleme/i)).toBeInTheDocument();
    });

    it("0 saniye önce güncellendi mesajı doğru format gösterir", () => {
      const now = Date.now();
      render(<TripFilters {...defaultProps} dataUpdatedAt={now} />);
      expect(screen.getByText(/0 sn önce/i)).toBeInTheDocument();
    });
  });

  describe("arama kutusu", () => {
    it("arama kutusunu render eder", () => {
      render(<TripFilters {...defaultProps} />);
      expect(
        screen.getByPlaceholderText(/sefer numarası/i),
      ).toBeInTheDocument();
    });

    it("yazı yazılınca setFilters çağrılır", () => {
      render(<TripFilters {...defaultProps} />);
      fireEvent.change(screen.getByPlaceholderText(/sefer numarası/i), {
        target: { value: "İstanbul" },
      });
      expect(mockSetFilters).toHaveBeenCalledWith({ search: "İstanbul" });
    });
  });

  describe("DataExportImport bileşeni", () => {
    it("toolbar alanında render edilir", () => {
      render(<TripFilters {...defaultProps} />);
      expect(screen.getByTestId("export-import")).toBeInTheDocument();
    });
  });
});
