import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "../../../test/test-utils";
import { DriverFilters } from "../DriverFilters";

function setup(overrides: Partial<Parameters<typeof DriverFilters>[0]> = {}) {
  const props = {
    search: "",
    setSearch: vi.fn(),
    viewMode: "grid" as const,
    setViewMode: vi.fn(),
    aktifOnly: true,
    setAktifOnly: vi.fn(),
    ehliyetFilter: "",
    setEhliyetFilter: vi.fn(),
    ehliyetOptions: ["", "B", "C", "CE", "D", "D1E", "E"],
    minScore: 0.1,
    setMinScore: vi.fn(),
    maxScore: 2.0,
    setMaxScore: vi.fn(),
    ...overrides,
  };
  render(<DriverFilters {...props} />);
  return props;
}

describe("DriverFilters", () => {
  it("search input ve görünüm toggle render edilir", () => {
    setup();
    expect(
      screen.getByPlaceholderText("İsim veya telefon ara..."),
    ).toBeInTheDocument();
    expect(screen.getByText("Liste")).toBeInTheDocument();
    expect(screen.getByText("Kartlar")).toBeInTheDocument();
  });

  it("search input değiştirildiğinde setSearch çağrılır", () => {
    const props = setup();
    const input = screen.getByPlaceholderText(
      "İsim veya telefon ara...",
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "Ali" } });
    expect(props.setSearch).toHaveBeenCalledWith("Ali");
  });

  it("min/max skor input range içinde clamp eder", () => {
    const props = setup({ minScore: 0.5, maxScore: 1.5 });
    // Min 2.5 girilirse clamp(0.1, 2.0) sonrası Math.min(2.0, 1.5) = 1.5
    const minNumber = screen.getByLabelText("Min") as HTMLInputElement;
    fireEvent.change(minNumber, { target: { value: "2.5" } });
    expect(props.setMinScore).toHaveBeenLastCalledWith(1.5);
  });

  it("max < min olmaz: max yeterince düşürülürse min seviyesine eşitlenir", () => {
    const props = setup({ minScore: 1.2, maxScore: 1.5 });
    const maxNumber = screen.getByLabelText("Max") as HTMLInputElement;
    fireEvent.change(maxNumber, { target: { value: "0.5" } });
    // clamp(0.5, 0.1, 2.0) = 0.5; max = Math.max(0.5, 1.2) = 1.2
    expect(props.setMaxScore).toHaveBeenLastCalledWith(1.2);
  });

  it("Sıfırla butonu tüm filtreleri default değerlere döndürür", () => {
    const props = setup({
      search: "foo",
      ehliyetFilter: "CE",
      aktifOnly: false,
      minScore: 0.5,
      maxScore: 1.5,
    });
    fireEvent.click(screen.getByText("Sıfırla"));
    expect(props.setSearch).toHaveBeenCalledWith("");
    expect(props.setEhliyetFilter).toHaveBeenCalledWith("");
    expect(props.setAktifOnly).toHaveBeenCalledWith(true);
    expect(props.setMinScore).toHaveBeenCalledWith(0.1);
    expect(props.setMaxScore).toHaveBeenCalledWith(2.0);
  });
});
