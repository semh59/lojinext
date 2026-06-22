import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";

// Hooks/services that the embedded pages will call — mock them.
vi.mock("../../api/today", () => ({
  todayService: {
    getTriage: vi.fn().mockResolvedValue({
      critical_count: 0,
      pending_count: 0,
      items: [],
      active_trips_count: 0,
      completed_today_count: 0,
      computed_at: new Date().toISOString(),
    }),
  },
}));

vi.mock("../../context/AuthContext", () => ({
  useAuth: vi.fn(),
  AuthProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("../DashboardPage", () => ({
  default: () => <div data-testid="legacy-dashboard">Eski Dashboard</div>,
}));

vi.mock("../TodayPage", () => ({
  default: () => <div data-testid="today-page">Bugün</div>,
}));

import HomePage from "../HomePage";
import { useAuth } from "../../context/AuthContext";

function renderWith() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("HomePage — RV2.9 hibrit `/` route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("admin → TodayPage render edilir", async () => {
    (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
      user: { role: "admin" },
    });
    renderWith();
    await waitFor(() =>
      expect(screen.getByTestId("today-page")).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("legacy-dashboard")).not.toBeInTheDocument();
  });

  it("user (non-triage) → DashboardPage render edilir", async () => {
    (useAuth as ReturnType<typeof vi.fn>).mockReturnValue({
      user: { role: "user" },
    });
    renderWith();
    await waitFor(() =>
      expect(screen.getByTestId("legacy-dashboard")).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("today-page")).not.toBeInTheDocument();
  });
});
