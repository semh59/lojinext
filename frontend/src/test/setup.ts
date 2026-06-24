import "@testing-library/jest-dom";

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
