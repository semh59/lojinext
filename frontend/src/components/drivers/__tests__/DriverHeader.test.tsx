import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "../../../test/test-utils";
import { DriverHeader } from "../DriverHeader";

describe("DriverHeader", () => {
  it("Yeni Şoför Ekle butonu render edilir ve onAdd çağrılır", () => {
    const onAdd = vi.fn();
    render(
      <DriverHeader
        onAdd={onAdd}
        onExport={vi.fn(async () => {})}
        onDownloadTemplate={vi.fn(async () => {})}
        onImport={vi.fn(async () => {})}
      />,
    );

    const button = screen.getByRole("button", { name: /Yeni Şoför Ekle/ });
    fireEvent.click(button);
    expect(onAdd).toHaveBeenCalledTimes(1);
  });

  it("Import/Export toolbar butonu render edilir", () => {
    render(
      <DriverHeader
        onAdd={vi.fn()}
        onExport={vi.fn(async () => {})}
        onDownloadTemplate={vi.fn(async () => {})}
        onImport={vi.fn(async () => {})}
      />,
    );
    // DataExportImport toolbar button (Veri Aktar/şablon vs. — bileşendeki string)
    expect(screen.getAllByRole("button").length).toBeGreaterThanOrEqual(2);
  });
});
