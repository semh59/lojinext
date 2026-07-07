import "@testing-library/jest-dom";
import { configure } from "@testing-library/react";

// waitFor/findBy varsayılanı 1s — real-backend (0-mock Faz 2) suit'lerinde
// tam-suite yükü altında gerçek HTTP cevapları 1s'i rahat aşıyor ve
// yük-bağımlı sahte timeout üretiyordu (örn. KullanicilarPage rol-option
// bekleyişi, 2026-07-05 tam koşumu). Geçen testler yavaşlamaz; yalnız
// failure tespiti gecikir.
configure({ asyncUtilTimeout: 5000 });

// Initialise i18next once for the whole test run so components that read
// translations via useTranslation()/t() resolve real strings (default locale
// tr) instead of returning the raw key. Without this, t()-based components
// render translation keys and text assertions fail.
import "../i18n";

// Polyfill for ResizeObserver
class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = ResizeObserver;

// Polyfill for matchMedia
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Polyfill for HTMLDialogElement (for Modal) - though usually JSDOM has basics, sometimes showModal is missing
if (!window.HTMLDialogElement) {
  // @ts-ignore
  window.HTMLDialogElement = function () {};
}
