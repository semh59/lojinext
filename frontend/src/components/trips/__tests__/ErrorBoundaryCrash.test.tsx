import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ErrorBoundary from "../../common/ErrorBoundary";

const originalConsoleError = console.error;

beforeEach(() => {
  console.error = vi.fn();
});

afterEach(() => {
  console.error = originalConsoleError;
});

function CrashingComponent(): JSX.Element {
  throw new Error("Test crash: component render failed");
}

describe("ErrorBoundary - Crash Scenario Tests", () => {
  it("catches render error and shows fallback UI", () => {
    render(
      <ErrorBoundary>
        <CrashingComponent />
      </ErrorBoundary>,
    );

    expect(
      screen.getByRole("heading", { name: /sistem kesintisi/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/beklenmedik bir hata tespit edildi/i),
    ).toBeInTheDocument();
  });

  it('shows "Sistemi Yeniden Baslat" button in fallback', () => {
    render(
      <ErrorBoundary>
        <CrashingComponent />
      </ErrorBoundary>,
    );

    expect(
      screen.getByRole("button", { name: /sistemi yeniden ba\u015flat/i }),
    ).toBeInTheDocument();
  });

  it('shows "Ana Sayfaya Don" button in fallback', () => {
    render(
      <ErrorBoundary>
        <CrashingComponent />
      </ErrorBoundary>,
    );

    expect(
      screen.getByRole("button", { name: /ana sayfaya d\u00f6n/i }),
    ).toBeInTheDocument();
  });

  it("calls console.error via componentDidCatch", () => {
    render(
      <ErrorBoundary>
        <CrashingComponent />
      </ErrorBoundary>,
    );

    expect(console.error).toHaveBeenCalled();
  });

  it("renders children normally when no error occurs", () => {
    render(
      <ErrorBoundary>
        <div data-testid="safe-child">Safe Content</div>
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("safe-child")).toBeInTheDocument();
    expect(screen.getByText("Safe Content")).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /sistem kesintisi/i }),
    ).not.toBeInTheDocument();
  });

  it("uses custom fallback when provided", () => {
    const customFallback = (
      <div data-testid="custom-fallback">Ozel Hata Mesaji</div>
    );

    render(
      <ErrorBoundary fallback={customFallback}>
        <CrashingComponent />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("custom-fallback")).toBeInTheDocument();
    expect(screen.getByText("Ozel Hata Mesaji")).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /sistem kesintisi/i }),
    ).not.toBeInTheDocument();
  });

  it("shows error details in DEV mode", () => {
    render(
      <ErrorBoundary>
        <CrashingComponent />
      </ErrorBoundary>,
    );

    expect(
      screen.getAllByText(/test crash: component render failed/i).length,
    ).toBeGreaterThan(0);
  });

  it("documents that ErrorBoundary prevents white screen fallback", () => {
    const { container } = render(
      <ErrorBoundary>
        <CrashingComponent />
      </ErrorBoundary>,
    );

    expect(container.innerHTML).not.toBe("");
    expect(
      screen.getByRole("heading", { name: /sistem kesintisi/i }),
    ).toBeInTheDocument();
  });
});
