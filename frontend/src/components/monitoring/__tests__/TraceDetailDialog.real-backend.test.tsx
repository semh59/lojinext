/**
 * 0-mock epiği: TraceDetailDialog.test.tsx'in mock'lu senaryolarına ek
 * olarak, gerçek backend'e karşı seed gerektirmeyen bir senaryo — gerçek
 * bir trace_id yokken GET /system/debug/trace/{id} gerçekten
 * {errors:[],audit:[],hint:...} döner (curl ile doğrulandı). Seed edilmiş
 * hata/audit zinciri (happy-path, 2 hata + 1 audit) mock'lu dosyada kalıyor
 * çünkü test DB'sinde error_logs/admin_audit_log'a gerçek bir zincir
 * üretmek pratik değil (bkz DriverRouteProfile emsali — aynı gerekçe).
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("TraceDetailDialog (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let TraceDetailDialog: typeof import("../TraceDetailDialog").TraceDetailDialog;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ TraceDetailDialog } = await import("../TraceDetailDialog"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("var olmayan trace_id → gerçek backend boş zincir + hint döner", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(
      <TraceDetailDialog
        traceId={`zm-real-backend-nonexistent-${Date.now()}`}
        onClose={() => {}}
      />,
    );

    await waitFor(
      () => expect(screen.getByText(/make trace/)).toBeInTheDocument(),
      {
        timeout: 10000,
      },
    );
    expect(screen.queryByTestId("trace-error-block")).not.toBeInTheDocument();
  }, 15000);
});
