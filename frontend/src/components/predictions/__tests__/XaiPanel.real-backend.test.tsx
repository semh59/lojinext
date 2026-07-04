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

    sessionStorage.setItem("access_token", authToken);
    fireEvent.click(screen.getByRole("button", { name: "Tahmin Et + Açıkla" }));

    await waitFor(
      () => {
        expect(screen.getByText(/Tahmini Tüketim:/)).toBeInTheDocument();
        expect(screen.getByText("Etki Faktörleri")).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
    // Gerçek backend contributions anahtarı "Yük" döner (bkz curl kanıtı).
    expect(screen.getByText("Yük")).toBeInTheDocument();
    // 0.0 L/100km olmadığını doğrula (regresyonun tam tersini kanıtla).
    expect(screen.queryByText("0.0 L/100km")).not.toBeInTheDocument();
  }, 15000);
});
