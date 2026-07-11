import { render, screen, fireEvent } from "../../../test/test-utils";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { VehicleFilters } from "../VehicleFilters";
import { vehicleFilterText } from "../../../resources/tr/vehicles";

// framer-motion passthrough
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, className, ...rest }: any) => (
      <div className={className} {...rest}>
        {children}
      </div>
    ),
  },
}));

const defaultFilters = {
  marka: "",
  model: "",
  min_yil: "",
  max_yil: "",
};

const buildProps = (
  overrides: Partial<Parameters<typeof VehicleFilters>[0]> = {},
) => ({
  search: "",
  setSearch: vi.fn(),
  showOnlyActive: false,
  setShowOnlyActive: vi.fn(),
  isFilterOpen: false,
  setIsFilterOpen: vi.fn(),
  filters: { ...defaultFilters },
  setFilters: vi.fn(),
  ...overrides,
});

describe("VehicleFilters", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders search input with correct placeholder", () => {
    render(<VehicleFilters {...buildProps()} />);
    expect(
      screen.getByPlaceholderText(vehicleFilterText.searchPlaceholder),
    ).toBeInTheDocument();
  });

  it("calls setSearch when typing in search input", () => {
    const setSearch = vi.fn();
    render(<VehicleFilters {...buildProps({ setSearch })} />);
    fireEvent.change(
      screen.getByPlaceholderText(vehicleFilterText.searchPlaceholder),
      { target: { value: "Mercedes" } },
    );
    expect(setSearch).toHaveBeenCalledWith("Mercedes");
  });

  it("renders 'Aktif Araçlar' toggle button", () => {
    render(<VehicleFilters {...buildProps()} />);
    expect(screen.getByText(vehicleFilterText.activeOnly)).toBeInTheDocument();
  });

  it("calls setShowOnlyActive when active-only button is clicked", () => {
    const setShowOnlyActive = vi.fn();
    render(<VehicleFilters {...buildProps({ setShowOnlyActive })} />);
    fireEvent.click(screen.getByText(vehicleFilterText.activeOnly));
    expect(setShowOnlyActive).toHaveBeenCalledWith(true);
  });

  it("renders 'Detaylı Filtre' toggle button", () => {
    render(<VehicleFilters {...buildProps()} />);
    expect(
      screen.getByText(vehicleFilterText.advancedFilters),
    ).toBeInTheDocument();
  });

  it("calls setIsFilterOpen when advanced filter button is clicked", () => {
    const setIsFilterOpen = vi.fn();
    render(<VehicleFilters {...buildProps({ setIsFilterOpen })} />);
    fireEvent.click(screen.getByText(vehicleFilterText.advancedFilters));
    expect(setIsFilterOpen).toHaveBeenCalledWith(true);
  });

  it("does NOT render filter fields when isFilterOpen=false", () => {
    render(<VehicleFilters {...buildProps({ isFilterOpen: false })} />);
    expect(
      screen.queryByPlaceholderText(vehicleFilterText.placeholders.brand),
    ).not.toBeInTheDocument();
  });

  it("renders brand/model/year filter inputs when isFilterOpen=true", () => {
    render(<VehicleFilters {...buildProps({ isFilterOpen: true })} />);
    expect(
      screen.getByPlaceholderText(vehicleFilterText.placeholders.brand),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(vehicleFilterText.placeholders.model),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(vehicleFilterText.placeholders.minYear),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(vehicleFilterText.placeholders.maxYear),
    ).toBeInTheDocument();
  });

  it("renders Uygula and Temizle buttons when filter panel is open", () => {
    render(<VehicleFilters {...buildProps({ isFilterOpen: true })} />);
    expect(screen.getByText(vehicleFilterText.apply)).toBeInTheDocument();
    expect(screen.getByText(vehicleFilterText.reset)).toBeInTheDocument();
  });

  it("calls setIsFilterOpen(false) when Uygula is clicked", () => {
    const setIsFilterOpen = vi.fn();
    render(
      <VehicleFilters
        {...buildProps({ isFilterOpen: true, setIsFilterOpen })}
      />,
    );
    fireEvent.click(screen.getByText(vehicleFilterText.apply));
    expect(setIsFilterOpen).toHaveBeenCalledWith(false);
  });

  it("calls setFilters with a merged plain object when typing brand/model/year, not an updater function", () => {
    // Regression: onChange handlers called setFilters with a React-updater
    // callback `(current) => ({...current, marka: value})`. The real
    // setFilters prop (VehiclesModule.tsx wires it to useUrlState) only
    // accepts a plain object — spreading a function produces `{}`, so
    // every keystroke silently dropped marka/model/min_yil/max_yil.
    const setFilters = vi.fn();
    render(
      <VehicleFilters {...buildProps({ isFilterOpen: true, setFilters })} />,
    );

    fireEvent.change(
      screen.getByPlaceholderText(vehicleFilterText.placeholders.brand),
      { target: { value: "Volvo" } },
    );

    expect(setFilters).toHaveBeenCalledWith({
      ...defaultFilters,
      marka: "Volvo",
    });
    expect(typeof setFilters.mock.calls[0][0]).not.toBe("function");
  });

  it("resets filters and search when Temizle is clicked", () => {
    const setFilters = vi.fn();
    const setSearch = vi.fn();
    render(
      <VehicleFilters
        {...buildProps({ isFilterOpen: true, setFilters, setSearch })}
      />,
    );
    fireEvent.click(screen.getByText(vehicleFilterText.reset));
    expect(setFilters).toHaveBeenCalledWith(defaultFilters);
    expect(setSearch).toHaveBeenCalledWith("");
  });

  it("renders filter field labels when panel is open", () => {
    render(<VehicleFilters {...buildProps({ isFilterOpen: true })} />);
    expect(
      screen.getByText(vehicleFilterText.fields.brand),
    ).toBeInTheDocument();
    expect(
      screen.getByText(vehicleFilterText.fields.model),
    ).toBeInTheDocument();
    expect(
      screen.getByText(vehicleFilterText.fields.minYear),
    ).toBeInTheDocument();
    expect(
      screen.getByText(vehicleFilterText.fields.maxYear),
    ).toBeInTheDocument();
  });
});
