import { render, screen } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../../context/AuthContext";
import { TripTable } from "../TripTable";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
}));

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: (args: any) => {
    const count = args?.count ?? 0;
    return {
      getTotalSize: () => count * 140,
      getVirtualItems: () =>
        Array.from({ length: count }).map((_, index) => ({
          key: `row-${index}`,
          index,
          size: 140,
          start: index * 140,
        })),
    };
  },
}));

const noop = () => {};

function withAuth(ui: React.ReactElement) {
  return render(
    <MemoryRouter>
      <AuthProvider>{ui}</AuthProvider>
    </MemoryRouter>,
  );
}

describe("TripTable - Empty State Render", () => {
  it('renders "Henüz Sefer Yok" when trips array is empty', () => {
    withAuth(
      <TripTable trips={[]} isLoading={false} onEdit={noop} onDelete={noop} />,
    );

    expect(
      screen.getByRole("heading", { name: /henüz sefer yok/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/aktif operasyonel sefer bulunmuyor/i),
    ).toBeInTheDocument();
  });

  it("renders loading skeletons when isLoading is true", () => {
    const { container } = withAuth(
      <TripTable trips={[]} isLoading={true} onEdit={noop} onDelete={noop} />,
    );

    expect(container.querySelectorAll(".skeleton").length).toBeGreaterThan(0);
  });

  it("does not render skeletons when isLoading is false and trips are empty", () => {
    const { container } = withAuth(
      <TripTable trips={[]} isLoading={false} onEdit={noop} onDelete={noop} />,
    );

    expect(container.querySelectorAll(".skeleton").length).toBe(0);
  });

  it("does not render pagination when trips are empty", () => {
    withAuth(
      <TripTable trips={[]} isLoading={false} onEdit={noop} onDelete={noop} />,
    );

    expect(screen.queryByText(/onceki/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/sonraki/i)).not.toBeInTheDocument();
  });

  it("renders the empty state icon container", () => {
    const { container } = withAuth(
      <TripTable trips={[]} isLoading={false} onEdit={noop} onDelete={noop} />,
    );

    expect(container.querySelector(".border-dashed")).toBeInTheDocument();
  });

  it("renders trip rows when trips are provided", () => {
    const mockTrip = {
      id: 1,
      tarih: "2026-01-01",
      saat: "10:00",
      arac_id: 1,
      sofor_id: 1,
      guzergah_id: 1,
      cikis_yeri: "İstanbul",
      varis_yeri: "Ankara",
      mesafe_km: 450,
      bos_agirlik_kg: 8000,
      dolu_agirlik_kg: 18000,
      net_kg: 10000,
      ton: 10,
      durum: "Tamamlandı",
    };

    withAuth(
      <TripTable
        trips={[mockTrip as any]}
        isLoading={false}
        onEdit={noop}
        onDelete={noop}
      />,
    );

    expect(
      screen.queryByRole("heading", { name: /henüz sefer yok/i }),
    ).not.toBeInTheDocument();

    expect(
      screen.getByText(
        (_, element) =>
          element?.tagName.toLowerCase() === "h4" &&
          element.textContent?.includes("İstanbul") &&
          element.textContent?.includes("Ankara") === true,
      ),
    ).toBeInTheDocument();
  });
});
