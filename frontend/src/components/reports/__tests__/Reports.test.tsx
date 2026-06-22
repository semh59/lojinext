import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  reportCardsText,
  reportDownloadOptions,
} from "../../../resources/tr/reports";
import { ReportCards } from "../ReportCards";

describe("ReportCards", () => {
  it("renders all cards", () => {
    render(<ReportCards onDownload={vi.fn()} />);
    expect(
      screen.getByText(reportDownloadOptions.fleet_summary.cardTitle),
    ).toBeInTheDocument();
    expect(
      screen.getByText(reportDownloadOptions.vehicle_detail.cardTitle),
    ).toBeInTheDocument();
  });

  it("calls onDownload when clicked", () => {
    const handleDownload = vi.fn();
    render(<ReportCards onDownload={handleDownload} />);
    const buttons = screen.getAllByText(reportCardsText.downloadButton);
    fireEvent.click(buttons[0]);
    expect(handleDownload).toHaveBeenCalledWith("fleet_summary");
  });
});
