/**
 * 0-mock epiği: WhatIfPanel.test.tsx'in mock'lu senaryolarına ek olarak,
 * gerçek backend'e karşı seed gerektirmeyen senaryo — boş DB'de
 * `POST /reports/executive/what-if` (fleet_renewal) deterministik olarak
 * yearly_savings_tl=0 + reasons=["Bu yaş eşiğinin üstünde aktif araç yok"]
 * döner (curl ile doğrulandı, default input'larla: max_age_years=15).
 *
 * "fleet_renewal happy path" (spesifik ROI/payback rakamları) ve "Monte
 * Carlo P10/P50/P90" senaryoları gerçek araç/güzergah verisi seed'i
 * gerektirir — mock'lu dosyada kalıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("WhatIfPanel (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let WhatIfPanel: typeof import("../WhatIfPanel").WhatIfPanel;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor, fireEvent } = await import(
      "../../../test/test-utils"
    ));
    ({ WhatIfPanel } = await import("../WhatIfPanel"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("boş filo + default fleet_renewal → gerçek backend 'araç yok' nedeni", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<WhatIfPanel />);
    fireEvent.click(
      screen.getByRole("button", { name: /Senaryoyu Çalıştır/i }),
    );
    await waitFor(
      () =>
        expect(
          screen.getByText(/Bu yaş eşiğinin üstünde aktif araç yok/),
        ).toBeInTheDocument(),
      { timeout: 10000 },
    );
    expect(screen.getByText("₺0")).toBeInTheDocument();
  }, 15000);
});
