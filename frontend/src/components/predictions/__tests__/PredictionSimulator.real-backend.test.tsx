/**
 * 0-mock epiği: PredictionSimulator.test.tsx'in mock'lu senaryolarına ek
 * olarak, gerçek backend'e karşı bir senaryo. Bileşen gerçek araç/şoför
 * listesini çeker ve gerçek `/predictions/predict` endpoint'ini çağırır.
 * Zorluk/açıklama vb. hata-enjeksiyonlu senaryolar mock'lu dosyada kalıyor
 * (gerçek backend'te tetiklemesi pratik değil).
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

// Ağır bağımlılıkları stub'la — bunlar gerçek backend'le ilgisiz UI kütüphaneleri.
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
  },
}));
vi.mock("recharts", () => ({
  BarChart: ({ children }: any) => <div>{children}</div>,
  Bar: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
}));

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("PredictionSimulator (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let PredictionSimulator: typeof import("../PredictionSimulator").PredictionSimulator;
  let authToken: string;
  let vehicleId: number;
  let plaka: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor, fireEvent } = await import(
      "../../../test/test-utils"
    ));
    ({ PredictionSimulator } = await import("../PredictionSimulator"));

    const suffix = String(Date.now()).slice(-4);
    plaka = `34 PS ${suffix}`;
    const createResp = await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({ plaka, marka: "Test Marka", aktif: true }),
    });
    const created = await createResp.json();
    vehicleId = created.id;
  });

  afterAll(async () => {
    if (vehicleId) {
      await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/${vehicleId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${authToken}` },
      }).catch(() => {});
    }
    vi.unstubAllEnvs();
  });

  it("gerçek araç listesini yükler ve gerçek predict çağrısıyla sonuç gösterir", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<PredictionSimulator />);

    await waitFor(() => expect(screen.getByText(plaka)).toBeInTheDocument(), {
      timeout: 10000,
    });

    const vehicleSelect = screen.getAllByRole("combobox")[0];
    fireEvent.change(vehicleSelect, { target: { value: String(vehicleId) } });

    const submitBtn = screen.getByRole("button", { name: "Tahmini Hesapla" });
    expect(submitBtn).not.toBeDisabled();
    sessionStorage.setItem("access_token", authToken);
    fireEvent.click(submitBtn);

    await waitFor(
      () => expect(screen.getByText(/Tahmin Sonucu/)).toBeInTheDocument(),
      { timeout: 10000 },
    );
  }, 15000);
});
