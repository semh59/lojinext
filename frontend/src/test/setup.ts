import "@testing-library/jest-dom";

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
