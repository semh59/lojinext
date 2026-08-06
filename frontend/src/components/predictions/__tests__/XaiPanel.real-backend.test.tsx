/**
 * 0-mock epiği: XaiPanel.test.tsx'in mock'lu senaryolarına ek olarak,
 * gerçek backend'e karşı bir senaryo. Gerçek `/predictions/ensemble/status`
 * ve `/predictions/explain` çağrıları egzersiz edilir.
 *
 * Bu dosya yazılırken GERÇEK BİR PROD BUG bulundu ve düzeltildi:
 * `ExplainPredictionResponse` şeması (app/schemas/api_responses.py) gerçekte
 * `{prediction, unit, contributions, confidence}` döner — `tahmini_tuketim`/
 * `components` DEĞİL. XaiPanel.tsx ve XaiExplainPanel.tsx bu yanlış alan
 * adlarını okuyordu; sonuç her zaman "0.0 L/100km" + boş etki faktörleri
 * gösteriyordu (curl ile doğrulandı, mock'lu testler yanlış alan adlarıyla
 * sahte-yeşil kalmıştı). Her iki bileşen de artık gerçek alanları (`prediction`/
 * `contributions`) okuyor, eski adlar geriye-dönük uyumluluk için fallback.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
  },
}));

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("XaiPanel (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let XaiPanel: typeof import("../XaiPanel").XaiPanel;
  let EnsembleWeightsPanel: typeof import("../XaiPanel").EnsembleWeightsPanel;
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
    ({ XaiPanel, EnsembleWeightsPanel } = await import("../XaiPanel"));

    const suffix = String(Date.now()).slice(-4);
    plaka = `34 XP ${suffix}`;
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

  it("gerçek ensemble ağırlıklarını gösterir (physics=%80.0 en yüksek)", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<EnsembleWeightsPanel />);

    await waitFor(() => expect(screen.getByText("80.0%")).toBeInTheDocument(), {
      timeout: 10000,
    });
    expect(screen.getByText(/Toplam model: 5/)).toBeInTheDocument();
  }, 15000);

  it("gerçek explain çağrısı sonucunda tahmin değeri ve etki faktörleri gösterir (contributions alanı)", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<XaiPanel />);

    await waitFor(() => expect(screen.getByText(plaka)).toBeInTheDocument(), {
      timeout: 10000,
    });

    const vehicleSelect = screen.getByRole("combobox");
    fireEvent.change(vehicleSelect, { target: { value: String(vehicleId) } });

    // Yük (ton) alanını sıfırdan farklı yap — backend "Yük" katkısını
    // yalnızca ton > 0 iken döner (curl ile doğrulandı: ton=0 → sadece
    // "ML Düzeltmesi" katkısı gelir). Alan sırası: Mesafe, Yük, Tırmanış, İniş.
    const numberInputs = screen.getAllByRole("spinbutton");
    fireEvent.change(numberInputs[1], { target: { value: "10" } });

    // The prediction_ml_service circuit breaker (reset_timeout=60s,
    // fail_max=5) is a process-wide singleton -- unrelated real-backend
    // tests earlier in this suite can leave it OPEN (observed twice in
    // CI: 2026-08-05). A real user in that situation just clicks the
    // predict button again (see XaiPanel.tsx:200-208, the button stays
    // enabled after isError) -- retry across a window wider than the
    // breaker's own reset_timeout instead of masking the flake.
    const resultLabel = "Tahmini Tüketim:";
    const errorLabel = "Tahmin hesaplanamadı";
    const buttonLabel = "Tahmin Et + Açıkla";
    const contributionsLabel = "Etki Faktörleri";
    const loadLabel = "Yük";

    const clickAndWaitForResult = async () => {
      sessionStorage.setItem("access_token", authToken);
      fireEvent.click(screen.getByRole("button", { name: buttonLabel }));
      await waitFor(
        () => {
          const hasResult =
            screen.queryAllByText((text) => text.includes(resultLabel)).length >
            0;
          const hasError =
            screen.queryAllByText((text) => text.includes(errorLabel)).length >
            0;
          expect(hasResult || hasError).toBe(true);
        },
        { timeout: 8000 },
      );
      return (
        screen.queryAllByText((text) => text.includes(resultLabel)).length > 0
      );
    };

    // Retry budget wall-clock: wide enough to span the breaker's own
    // reset_timeout (60s) plus margin for a half-open probe to succeed.
    const retryDeadline = Date.now() + 75000;
    let succeeded = await clickAndWaitForResult();
    while (!succeeded && Date.now() < retryDeadline) {
      await new Promise((resolve) => setTimeout(resolve, 5000));
      succeeded = await clickAndWaitForResult();
    }
    expect(succeeded).toBe(true);

    expect(screen.getByText(contributionsLabel)).toBeInTheDocument();
    // Real backend's contributions key comes back as loadLabel (verified via curl).
    expect(screen.getByText(loadLabel)).toBeInTheDocument();
    // Confirm it's not 0.0 L/100km (the exact opposite of the original regression).
    expect(screen.queryByText("0.0 L/100km")).not.toBeInTheDocument();
  }, 100000);
});
