import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "../../../test/test-utils";
import { TriageItemCard } from "../TriageItemCard";
import type { TriageItem } from "../../../api/today";

const navigateMock = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual: any = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => navigateMock };
});

const baseCritical: TriageItem = {
  id: "anomaly:42",
  category: "anomaly",
  severity: "critical",
  title: "Yakıt sapma %45",
  subtitle: "High suspicion test anomaly",
  timestamp: new Date(Date.now() - 30 * 60_000).toISOString(),
  plaka: "34 ABC 123",
  actions: [{ label: "İncele", url: "/alerts?id=42", action_type: "navigate" }],
};

describe("TriageItemCard", () => {
  it("critical → kırmızı sol bant + Kritik rozeti", () => {
    render(<TriageItemCard item={baseCritical} />);
    expect(screen.getByText("Yakıt sapma %45")).toBeInTheDocument();
    expect(screen.getByText("Kritik")).toBeInTheDocument();
    expect(screen.getByText("34 ABC 123")).toBeInTheDocument();
  });

  it("time ago format — 30 dk önce", () => {
    render(<TriageItemCard item={baseCritical} />);
    expect(screen.getByText("30 dk önce")).toBeInTheDocument();
  });

  it("action click → navigate çağrılır", () => {
    navigateMock.mockClear();
    render(<TriageItemCard item={baseCritical} />);
    fireEvent.click(screen.getByRole("button", { name: /İncele/i }));
    expect(navigateMock).toHaveBeenCalledWith("/alerts?id=42");
  });

  it("low severity → yeşil ton, Düşük rozeti", () => {
    render(<TriageItemCard item={{ ...baseCritical, severity: "low" }} />);
    expect(screen.getByText("Düşük")).toBeInTheDocument();
  });

  it("boş subtitle → render edilmez", () => {
    const { container } = render(
      <TriageItemCard item={{ ...baseCritical, subtitle: "" }} />,
    );
    // Subtitle p elementi yok
    expect(container.textContent).not.toContain("High suspicion");
  });

  it("plaka null → bölüm gizli", () => {
    render(<TriageItemCard item={{ ...baseCritical, plaka: null }} />);
    // Plaka span'i görünmez
    expect(screen.queryByText("34 ABC 123")).not.toBeInTheDocument();
  });
});
