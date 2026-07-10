import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render } from "../../../test/test-utils";
import AdminLayout from "../AdminLayout";

// Regression test: AdminLayout never applied the user's saved dark-mode
// preference — useDarkMode() was only ever called inside AppLayout.tsx.
// Landing directly on an admin page (fresh tab, hard refresh, bookmark)
// skipped AppLayout's mount effect entirely, so localStorage could say
// "dark" while <html> never got the "dark" class — the whole admin panel
// silently rendered in light mode regardless of the saved preference.

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
  },
}));

vi.mock("react-router-dom", async () => {
  const actual =
    await vi.importActual<typeof import("react-router-dom")>(
      "react-router-dom",
    );
  return {
    ...actual,
    Outlet: () => <div data-testid="admin-outlet">Admin Page Content</div>,
    useLocation: () => ({ pathname: "/admin" }),
  };
});

vi.mock("../../../context/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: 1,
      username: "testadmin",
      role: "admin",
      permissions: [],
    },
    logout: vi.fn(),
  }),
  AuthProvider: ({ children }: any) => <>{children}</>,
}));

describe("AdminLayout", () => {
  beforeEach(() => {
    document.documentElement.classList.remove("dark");
  });

  afterEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  it("applies the saved dark theme on mount, even without AppLayout ever mounting", () => {
    localStorage.setItem("theme", "dark");
    render(<AdminLayout />);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("applies the saved light theme on mount", () => {
    localStorage.setItem("theme", "light");
    document.documentElement.classList.add("dark");
    render(<AdminLayout />);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
