/**
 * 0-mock epiği: QuietHoursSettings.test.tsx'in mock'lu senaryosuna ek olarak,
 * gerçek backend'e karşı bir senaryo. Test ortamında yalnızca sistem
 * (synthetic super admin, id<=0) hesabı mevcut ve backend bu hesabın
 * `POST /preferences` çağırmasını kasıtlı olarak reddediyor
 * (`HTTP_403 "Sistem kullanıcısı tercih kaydedemez"` — curl ile doğrulandı,
 * gerçek bir iş kuralı, bug değil). Bu yüzden save round-trip senaryosu
 * normal bir kullanıcı hesabı gerektirir ve mock'lu dosyada kalıyor; burada
 * gerçek `GET /preferences/bildirim` çağrısının boş sonuçta varsayılan
 * saatleri koruduğunu (gerçek HTTP round-trip) doğruluyoruz.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("QuietHoursSettings (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let QuietHoursSettings: typeof import("../QuietHoursSettings").QuietHoursSettings;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen } = await import("../../../test/test-utils"));
    ({ QuietHoursSettings } = await import("../QuietHoursSettings"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("gerçek backend'den boş preference listesi dönünce varsayılan saatleri gösterir", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<QuietHoursSettings />);

    expect(await screen.findByDisplayValue("22:00")).toBeInTheDocument();
    expect(screen.getByDisplayValue("07:00")).toBeInTheDocument();
  }, 15000);
});
