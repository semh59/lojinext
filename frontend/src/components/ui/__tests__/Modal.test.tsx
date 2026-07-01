/**
 * 2026-07-01 prod-grade denetimi P2 (Dalga 4 madde 25): Modallerde
 * aria-modal zaten vardı ama focus-trap yoktu — WCAG 2.1 AA ihlali.
 * Bu test, paylaşılan `Modal` bileşeninin (12 tüketicisi var) açılışta
 * odağı diyalog içine taşıdığını, Tab/Shift+Tab'ın diyalog dışına
 * kaçmadığını (döngü yaptığını), kapanışta odağı tetikleyici elemana
 * geri verdiğini doğrular.
 */
import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Modal } from "../Modal";

function Harness() {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setIsOpen(true)}>Aç</button>
      <Modal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title="Test Modal"
      >
        <button>Birinci</button>
        <button>İkinci</button>
      </Modal>
    </div>
  );
}

describe("Modal — focus trap", () => {
  it("açılışta odağı diyalog içine taşır (dışarıda bir yerde kalmaz)", async () => {
    render(<Harness />);
    fireEvent.click(screen.getByText("Aç"));
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => {
      expect(dialog.contains(document.activeElement)).toBe(true);
    });
  });

  it("son odaklanabilir elemandan Tab basılınca odak diyaloğun ilk elemanına döner (dışarı kaçmaz)", async () => {
    render(<Harness />);
    fireEvent.click(screen.getByText("Aç"));
    await screen.findByRole("dialog");

    const closeBtn = screen.getByText("Kapat").closest("button")!;
    const second = screen.getByText("İkinci");
    second.focus();
    expect(document.activeElement).toBe(second);

    fireEvent.keyDown(second, { key: "Tab" });
    expect(document.activeElement).toBe(closeBtn);
  });

  it("ilk odaklanabilir elemandan Shift+Tab basılınca odak diyaloğun son elemanına döner", async () => {
    render(<Harness />);
    fireEvent.click(screen.getByText("Aç"));
    await screen.findByRole("dialog");

    const closeBtn = screen.getByText("Kapat").closest("button")!;
    const second = screen.getByText("İkinci");
    closeBtn.focus();
    expect(document.activeElement).toBe(closeBtn);

    fireEvent.keyDown(closeBtn, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(second);
  });

  it("kapanışta odağı tetikleyici elemana geri verir", async () => {
    render(<Harness />);
    const openBtn = screen.getByText("Aç");
    openBtn.focus();
    fireEvent.click(openBtn);
    await screen.findByRole("dialog");

    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() => {
      expect(document.activeElement).toBe(openBtn);
    });
  });
});
