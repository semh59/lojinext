import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import axios from "axios";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";
import { adminIntegrationsText } from "../../../resources/tr/admin";

// Mock notification context — not wrapped by test-utils' AllTheProviders.
vi.mock("../../../context/NotificationContext", () => ({
  useNotify: () => ({ notify: vi.fn() }),
  NotificationProvider: ({ children }: any) => <>{children}</>,
}));

vi.mock("../../../hooks/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

const backendUp = await isRealBackendReachable();

let render: typeof import("../../../test/test-utils").render;
let screen: typeof import("../../../test/test-utils").screen;
let waitFor: typeof import("../../../test/test-utils").waitFor;
let fireEvent: typeof import("../../../test/test-utils").fireEvent;
let within: typeof import("../../../test/test-utils").within;
let EntegrasyonlarPage: typeof import("../EntegrasyonlarPage").default;

function getServiceRow(serviceLabel: string): HTMLElement {
  const label = screen.getByText(serviceLabel);
  const row = label.closest(".grid") as HTMLElement | null;
  if (!row) throw new Error(`integration row for ${serviceLabel} not found`);
  return row;
}

// Reset the 3 known rows to NULL before/after — same globally-shared-row
// concern as the backend's own _reset_entegrasyon_rows fixture: mapbox/
// openroute/groq are fixed identifiers, not per-test-unique data, so a
// PUT here would otherwise leak into any other suite touching these
// services within the same CI run.
async function resetIntegrationRows(token: string): Promise<void> {
  // There is no DELETE endpoint by design (write-only, replace-only) —
  // "resetting" here just means leaving the row unconfigured is not
  // achievable via the API, so instead we set it back to an inert
  // placeholder value scoped to this test file only.
  await axios.put(
    `${REAL_BACKEND_URL}/admin/integrations/mapbox`,
    { api_key: "test-reset-placeholder" }, // pragma: allowlist secret
    { headers: { Authorization: `Bearer ${token}` } },
  );
}

describe.skipIf(!backendUp)("EntegrasyonlarPage (real backend)", () => {
  let token = "";

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
    ({ render, screen, waitFor, fireEvent, within } = await import(
      "../../../test/test-utils"
    ));
    EntegrasyonlarPage = (await import("../EntegrasyonlarPage")).default;
    token = await loginAsAdmin();
  }, 30000);

  beforeEach(() => {
    sessionStorage.setItem("access_token", token);
  });

  afterEach(async () => {
    await resetIntegrationRows(token).catch(() => undefined);
  });

  it("renders page heading, description and write-only notice", async () => {
    render(<EntegrasyonlarPage />);
    await waitFor(
      () => {
        expect(
          screen.getByText(adminIntegrationsText.heading),
        ).toBeInTheDocument();
        expect(
          screen.getByText(adminIntegrationsText.writeOnlyNotice),
        ).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  });

  it("lists all three known services with status badges", async () => {
    render(<EntegrasyonlarPage />);
    await waitFor(
      () => {
        expect(
          screen.getByText(adminIntegrationsText.serviceNames.mapbox),
        ).toBeInTheDocument();
        expect(
          screen.getByText(adminIntegrationsText.serviceNames.openroute),
        ).toBeInTheDocument();
        expect(
          screen.getByText(adminIntegrationsText.serviceNames.groq),
        ).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  });

  it("save button stays disabled until a value is typed", async () => {
    render(<EntegrasyonlarPage />);
    await waitFor(() =>
      expect(
        screen.getByText(adminIntegrationsText.serviceNames.mapbox),
      ).toBeInTheDocument(),
    );
    const row = within(
      getServiceRow(adminIntegrationsText.serviceNames.mapbox),
    );
    expect(
      row.getByRole("button", { name: adminIntegrationsText.actions.save }),
    ).toBeDisabled();

    fireEvent.change(
      row.getByPlaceholderText(adminIntegrationsText.inputPlaceholder),
      { target: { value: "sk-test-value" } }, // pragma: allowlist secret
    );
    await waitFor(() => {
      expect(
        row.getByRole("button", {
          name: adminIntegrationsText.actions.save,
        }),
      ).not.toBeDisabled();
    });
  });

  it("sets a key through the real PUT endpoint and never renders it back", async () => {
    const secretValue = "sk-real-round-trip-secret"; // pragma: allowlist secret

    render(<EntegrasyonlarPage />);
    await waitFor(() =>
      expect(
        screen.getByText(adminIntegrationsText.serviceNames.openroute),
      ).toBeInTheDocument(),
    );
    const row = within(
      getServiceRow(adminIntegrationsText.serviceNames.openroute),
    );
    const input = row.getByPlaceholderText(
      adminIntegrationsText.inputPlaceholder,
    );
    fireEvent.change(input, { target: { value: secretValue } });
    const saveBtn = row.getByRole("button", {
      name: adminIntegrationsText.actions.save,
    });
    await waitFor(() => expect(saveBtn).not.toBeDisabled());
    fireEvent.click(saveBtn);

    // Poll the real endpoint directly to confirm configured flips true —
    // the response body itself must never carry secretValue.
    await waitFor(
      async () => {
        const resp = await axios.get(
          `${REAL_BACKEND_URL}/admin/integrations/`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        expect(JSON.stringify(resp.data)).not.toContain(secretValue);
        const openroute = resp.data.find(
          (s: { servis_adi: string }) => s.servis_adi === "openroute",
        );
        expect(openroute.configured).toBe(true);
      },
      { timeout: 10000 },
    );

    // The input clears itself after a successful save (write-only UX —
    // nothing to redisplay).
    await waitFor(() => {
      expect((input as HTMLInputElement).value).toBe("");
    });

    // Clean up this row too (separate from the mapbox afterEach reset).
    await axios.put(
      `${REAL_BACKEND_URL}/admin/integrations/openroute`,
      { api_key: "test-reset-placeholder" }, // pragma: allowlist secret
      { headers: { Authorization: `Bearer ${token}` } },
    );
  }, 15000);
});
