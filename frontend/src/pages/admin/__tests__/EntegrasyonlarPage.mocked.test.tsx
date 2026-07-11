import { beforeEach, describe, expect, it, vi } from "vitest";
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
    getPlanned: vi.fn(),
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
  beforeEach(async () => {
    const { adminIntegrationsApi } = await import("../../../api/admin");
    (
      adminIntegrationsApi.getPlanned as ReturnType<typeof vi.fn>
    ).mockResolvedValue([]);
  });

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

describe("EntegrasyonlarPage (mocked — Faz 0 planned integrations section)", () => {
  it("shows AVL/fuel-card as not-implemented with their env var state", async () => {
    const { adminIntegrationsApi } = await import("../../../api/admin");
    (
      adminIntegrationsApi.getStatuses as ReturnType<typeof vi.fn>
    ).mockResolvedValue([]);
    (
      adminIntegrationsApi.getPlanned as ReturnType<typeof vi.fn>
    ).mockResolvedValue([
      {
        key: "avl",
        provider_env_var: "AVL_PROVIDER",
        provider_key: "mobiliz",
        implemented: false,
      },
      {
        key: "fuel_card",
        provider_env_var: "FUEL_PROVIDER",
        provider_key: null,
        implemented: false,
      },
    ]);

    render(<EntegrasyonlarPage />);
    await waitFor(() =>
      expect(
        screen.getByText(adminIntegrationsText.planned.heading),
      ).toBeInTheDocument(),
    );

    expect(
      screen.getByText(adminIntegrationsText.planned.names.avl),
    ).toBeInTheDocument();
    expect(
      screen.getByText(adminIntegrationsText.planned.names.fuel_card),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText(adminIntegrationsText.planned.notImplemented).length,
    ).toBe(2);

    // AVL: provider selected in .env, but adapter is still a stub.
    expect(
      screen.getByText(adminIntegrationsText.planned.providerSet("mobiliz")),
    ).toBeInTheDocument();
    // fuel_card: no provider selected at all.
    expect(
      screen.getByText(
        adminIntegrationsText.planned.providerNotSet("FUEL_PROVIDER"),
      ),
    ).toBeInTheDocument();
  });

  it("hides the planned-integrations section entirely when the list is empty", async () => {
    const { adminIntegrationsApi } = await import("../../../api/admin");
    (
      adminIntegrationsApi.getStatuses as ReturnType<typeof vi.fn>
    ).mockResolvedValue([]);
    (
      adminIntegrationsApi.getPlanned as ReturnType<typeof vi.fn>
    ).mockResolvedValue([]);

    render(<EntegrasyonlarPage />);
    await waitFor(() =>
      expect(
        screen.getByText(adminIntegrationsText.heading),
      ).toBeInTheDocument(),
    );

    expect(
      screen.queryByText(adminIntegrationsText.planned.heading),
    ).not.toBeInTheDocument();
  });
});
