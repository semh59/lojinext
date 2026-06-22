import { render, screen } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";

import { RequirePermission } from "../RequirePermission";

const { mockHasPermission, mockIsLoading } = vi.hoisted(() => ({
  mockHasPermission: vi.fn(),
  mockIsLoading: { value: false },
}));

vi.mock("../../../context/AuthContext", () => ({
  useAuth: () => ({
    hasPermission: mockHasPermission,
    isLoading: mockIsLoading.value,
  }),
}));

describe("RequirePermission", () => {
  beforeEach(() => {
    mockHasPermission.mockReset();
    mockIsLoading.value = false;
  });

  it("renders children when the user has the permission", () => {
    mockHasPermission.mockReturnValue(true);
    render(
      <RequirePermission permission="anomali:yonet">
        <button>Onayla</button>
      </RequirePermission>,
    );
    expect(screen.getByText("Onayla")).toBeInTheDocument();
    expect(mockHasPermission).toHaveBeenCalledWith("anomali:yonet");
  });

  it("hides children when the user lacks the permission", () => {
    mockHasPermission.mockReturnValue(false);
    render(
      <RequirePermission permission="anomali:yonet">
        <button>Onayla</button>
      </RequirePermission>,
    );
    expect(screen.queryByText("Onayla")).not.toBeInTheDocument();
  });

  it("renders the fallback when the permission is missing", () => {
    mockHasPermission.mockReturnValue(false);
    render(
      <RequirePermission
        permission="anomali:yonet"
        fallback={<span>read-only</span>}
      >
        <button>Onayla</button>
      </RequirePermission>,
    );
    expect(screen.getByText("read-only")).toBeInTheDocument();
    expect(screen.queryByText("Onayla")).not.toBeInTheDocument();
  });

  it("renders nothing while auth is loading", () => {
    mockHasPermission.mockReturnValue(true);
    mockIsLoading.value = true;
    const { container } = render(
      <RequirePermission permission="anomali:yonet">
        <button>Onayla</button>
      </RequirePermission>,
    );
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText("Onayla")).not.toBeInTheDocument();
  });
});
