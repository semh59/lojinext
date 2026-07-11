/**
 * Regression: same bug as VehicleFilters.tsx — onChange handlers called
 * setFilters with a React-updater callback `(current) => ({...current,
 * marka: value})`, but the real setFilters prop (TrailersModule.tsx wires
 * it to useUrlState) only accepts a plain object. Spreading a function
 * produces `{}`, so every keystroke silently dropped marka/model/min_yil/
 * max_yil — Brand/Model/Min Year/Max Year inputs looked like they
 * accepted no input at all.
 */
import { render, screen, fireEvent } from "../../../test/test-utils";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { TrailerFilters } from "../TrailerFilters";
import { trailerFilterText } from "../../../resources/tr/trailers";

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
  overrides: Partial<Parameters<typeof TrailerFilters>[0]> = {},
) => ({
  search: "",
  setSearch: vi.fn(),
  showOnlyActive: false,
  setShowOnlyActive: vi.fn(),
  isFilterOpen: true,
  setIsFilterOpen: vi.fn(),
  filters: { ...defaultFilters },
  setFilters: vi.fn(),
  viewMode: "grid" as const,
  setViewMode: vi.fn(),
  ...overrides,
});

describe("TrailerFilters", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls setFilters with a merged plain object when typing brand, not an updater function", () => {
    const setFilters = vi.fn();
    render(<TrailerFilters {...buildProps({ setFilters })} />);

    fireEvent.change(
      screen.getByPlaceholderText(trailerFilterText.placeholders.brand),
      { target: { value: "Krone" } },
    );

    expect(setFilters).toHaveBeenCalledWith({
      ...defaultFilters,
      marka: "Krone",
    });
    expect(typeof setFilters.mock.calls[0][0]).not.toBe("function");
  });

  it("calls setFilters with a merged plain object when typing max year, not an updater function", () => {
    const setFilters = vi.fn();
    render(<TrailerFilters {...buildProps({ setFilters })} />);

    fireEvent.change(
      screen.getByPlaceholderText(trailerFilterText.placeholders.maxYear),
      { target: { value: "2024" } },
    );

    expect(setFilters).toHaveBeenCalledWith({
      ...defaultFilters,
      max_yil: "2024",
    });
    expect(typeof setFilters.mock.calls[0][0]).not.toBe("function");
  });
});
