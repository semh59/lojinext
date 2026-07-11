import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "../../../test/test-utils";
import EntegrasyonlarPage from "../EntegrasyonlarPage";
import { adminIntegrationsText } from "../../../resources/tr/admin";

// Scenario kept mocked: the real backend's mapbox/openroute/groq rows are
// already `configured: true` in this dev environment (someone used the
// panel), so the env-fallback badge's exact trigger condition
// (!configured && env_fallback_configured) can't be reproduced against the
// real backend without overwriting the actual production-like keys — this
// write-only/replace-only API has no "unconfigure" endpoint to restore
// them afterward. See EntegrasyonlarPage.test.tsx for real-backend
// coverage of everything else on this page.

vi.mock("../../../api/admin", () => ({
  adminIntegrationsApi: {
    getStatuses: vi.fn(),
    updateKey: vi.fn(),
  },
}));

vi.mock("../../../context/NotificationContext", () => ({
  useNotify: () => ({ notify: vi.fn() }),
  NotificationProvider: ({ children }: any) => <>{children}</>,
}));

vi.mock("../../../hooks/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

function getServiceRow(serviceLabel: string): HTMLElement {
  const label = screen.getByText(serviceLabel);
  const row = label.closest(".grid") as HTMLElement | null;
  if (!row) throw new Error(`integration row for ${serviceLabel} not found`);
  return row;
}

describe("EntegrasyonlarPage (mocked — env-fallback badge scenario)", () => {
  it("shows the env-fallback badge when a service is not DB-configured but its env fallback is set", async () => {
    const { adminIntegrationsApi } = await import("../../../api/admin");
    (
      adminIntegrationsApi.getStatuses as ReturnType<typeof vi.fn>
    ).mockResolvedValue([
      {
        servis_adi: "mapbox",
        configured: false,
        guncellenme_tarihi: null,
        guncelleyen_id: null,
        container_running: null,
        container_health: null,
        env_fallback_configured: true,
      },
      {
        servis_adi: "openroute",
        configured: false,
        guncellenme_tarihi: null,
        guncelleyen_id: null,
        container_running: null,
        container_health: null,
        env_fallback_configured: false,
      },
    ]);

    render(<EntegrasyonlarPage />);
    await waitFor(() =>
      expect(
        screen.getByText(adminIntegrationsText.serviceNames.mapbox),
      ).toBeInTheDocument(),
    );

    // mapbox: not configured, but env fallback present -> badge shows.
    const mapboxRow = within(
      getServiceRow(adminIntegrationsText.serviceNames.mapbox),
    );
    expect(
      mapboxRow.getByText(adminIntegrationsText.envFallback.label),
    ).toBeInTheDocument();
    expect(
      mapboxRow.getByText(adminIntegrationsText.statusLabels.notConfigured),
    ).toBeInTheDocument();

    // openroute: not configured AND no env fallback -> badge stays hidden
    // (both signals already agree it's genuinely inactive).
    const openrouteRow = within(
      getServiceRow(adminIntegrationsText.serviceNames.openroute),
    );
    expect(
      openrouteRow.queryByText(adminIntegrationsText.envFallback.label),
    ).not.toBeInTheDocument();
  });

  it("hides the env-fallback badge once a service is DB-configured", async () => {
    const { adminIntegrationsApi } = await import("../../../api/admin");
    (
      adminIntegrationsApi.getStatuses as ReturnType<typeof vi.fn>
    ).mockResolvedValue([
      {
        servis_adi: "groq",
        configured: true,
        guncellenme_tarihi: "2026-07-10T10:00:00Z",
        guncelleyen_id: 1,
        container_running: null,
        container_health: null,
        env_fallback_configured: true,
      },
    ]);

    render(<EntegrasyonlarPage />);
    await waitFor(() =>
      expect(
        screen.getByText(adminIntegrationsText.serviceNames.groq),
      ).toBeInTheDocument(),
    );

    expect(
      screen.queryByText(adminIntegrationsText.envFallback.label),
    ).not.toBeInTheDocument();
  });
});
