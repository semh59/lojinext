/**
 * 0-mock epiği: ComplianceHeatmap.test.tsx'in mock'lu "empty" senaryosunun
 * gerçek karşılığı — bu test ortamının veritabanında araç/dorse
 * muayene kaydı olmadığı için `GET /reports/executive/compliance`
 * gerçekten total_items=0 döner (curl ile doğrulandı) → bileşen "yok"
 * mesajını gösterir.
 *
 * "overdue + soon counts" senaryosu (seeded muayene tarihli araç/dorse)
 * mock'lu dosyada kalıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("ComplianceHeatmap (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let ComplianceHeatmap: typeof import("../ComplianceHeatmap").ComplianceHeatmap;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ ComplianceHeatmap } = await import("../ComplianceHeatmap"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it('boş DB → gerçek backend "muayene yok" mesajı', async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<ComplianceHeatmap />);

    await waitFor(
      () => expect(screen.getByText(/muayene yok/i)).toBeInTheDocument(),
      { timeout: 10000 },
    );
  }, 15000);
});
