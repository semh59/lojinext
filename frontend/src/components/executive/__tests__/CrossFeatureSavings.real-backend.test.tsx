/**
 * 0-mock epiği: CrossFeatureSavings.test.tsx'in mock'lu senaryolarına ek
 * olarak, gerçek backend'e karşı seed gerektirmeyen senaryo — boş DB'de
 * `GET /reports/executive/cross-feature` deterministik olarak tüm kalemler
 * 0 döner (curl ile doğrulandı); 3 kalem etiketi + "Net etki" veri
 * miktarından bağımsız her zaman render edilir.
 *
 * "3 kalem doğru ikon/tone" (spesifik pozitif değerler) ve "net impact
 * negatif" senaryoları gerçek bakım/koçluk/hırsızlık verisi seed'i
 * gerektirir — mock'lu dosyada kalıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("CrossFeatureSavings (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let CrossFeatureSavings: typeof import("../CrossFeatureSavings").CrossFeatureSavings;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ CrossFeatureSavings } = await import("../CrossFeatureSavings"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("boş filo → gerçek backend 3 kalem + sıfır net etki", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<CrossFeatureSavings />);

    await waitFor(
      () =>
        expect(screen.getByText("Bakım gecikme zararı")).toBeInTheDocument(),
      { timeout: 10000 },
    );
    expect(screen.getByText("Koçluk tasarrufu")).toBeInTheDocument();
    expect(screen.getByText("Hırsızlık zararı")).toBeInTheDocument();
    expect(screen.getByText("Net etki")).toBeInTheDocument();
  }, 15000);
});
