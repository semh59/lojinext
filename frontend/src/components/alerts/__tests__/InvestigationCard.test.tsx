import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "../../../test/test-utils";
import { InvestigationCard } from "../InvestigationCard";
import type { Investigation } from "../../../api/investigations";

const baseInv: Investigation = {
  id: 1,
  anomaly_id: 10,
  status: "open",
  suspicion_score: 0.82,
  suspicion_level: "high",
  assigned_to_user_id: null,
  notes: null,
  resolution_type: null,
  evidence_files: [],
  created_at: new Date(Date.now() - 30 * 60_000).toISOString(),
  updated_at: new Date().toISOString(),
  closed_at: null,
  plaka: "34 ABC 123",
  sofor_adi: "Ali Veli",
  sapma_yuzde: 32.5,
};

describe("InvestigationCard", () => {
  it("high suspicion → Yüksek rozet + skor görünür", () => {
    render(<InvestigationCard investigation={baseInv} onClick={() => {}} />);
    expect(screen.getByText("Yüksek")).toBeInTheDocument();
    expect(screen.getByText("0.82")).toBeInTheDocument();
    expect(screen.getByText("34 ABC 123")).toBeInTheDocument();
    expect(screen.getByText("Ali Veli")).toBeInTheDocument();
    expect(screen.getByText("+32.5%")).toBeInTheDocument();
  });

  it('null suspicion_level → "Belirsiz"', () => {
    render(
      <InvestigationCard
        investigation={{
          ...baseInv,
          suspicion_level: null,
          suspicion_score: null,
        }}
        onClick={() => {}}
      />,
    );
    expect(screen.getByText("Belirsiz")).toBeInTheDocument();
  });

  it("tıklama → onClick çağrılır", () => {
    const fn = vi.fn();
    render(<InvestigationCard investigation={baseInv} onClick={fn} />);
    fireEvent.click(screen.getByRole("button"));
    expect(fn).toHaveBeenCalledTimes(1);
  });
});
