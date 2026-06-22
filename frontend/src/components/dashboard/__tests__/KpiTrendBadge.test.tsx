import { describe, expect, it } from "vitest";
import { render, screen } from "../../../test/test-utils";
import { KpiTrendBadge } from "../KpiTrendBadge";

describe("KpiTrendBadge", () => {
  it("pozitif değişimde + işaretli yüzdeyi gösterir", () => {
    render(<KpiTrendBadge trend={4.27} />);
    expect(screen.getByText("+4.3%")).toBeInTheDocument();
  });

  it("negatif değişimde eksi işaretli yüzdeyi gösterir", () => {
    render(<KpiTrendBadge trend={-2.5} />);
    expect(screen.getByText("-2.5%")).toBeInTheDocument();
  });

  it("sıfıra çok yakın değerleri 0% olarak gösterir", () => {
    render(<KpiTrendBadge trend={0.01} />);
    expect(screen.getByText("0.0%")).toBeInTheDocument();
  });

  it("null/undefined için render etmez", () => {
    const { container: c1 } = render(<KpiTrendBadge trend={null} />);
    const { container: c2 } = render(<KpiTrendBadge trend={undefined} />);
    expect(c1.firstChild).toBeNull();
    expect(c2.firstChild).toBeNull();
  });

  it("invert=true modunda pozitif değişim kötü kabul edilir", () => {
    render(<KpiTrendBadge trend={5} invert />);
    const badge = screen.getByText(/\+5\.0%/).closest("span");
    expect(badge?.className).toMatch(/text-danger/);
  });
});
