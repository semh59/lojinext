/**
 * 0-mock epiği: alerts domain. `investigationService.*` orval-generated
 * client'lar (`.../admin/investigations/*`) üzerinden gidiyor — baseURL
 * origin-only olmalı (REAL_BACKEND_ORIGIN).
 *
 * Orijinal dosyanın "açık soruşturma → detaylar görünür" ve "closed durum
 * → uyarı" testleri, id=42 önceden var olan bir Investigation kaydı
 * mock'luyordu. Gerçek backend'de investigation açmak için önce gerçek bir
 * Anomaly kaydı gerekiyor (`POST /admin/investigations` → `anomaly_id` FK
 * kontrolü, doğrulandı: var olmayan anomaly_id → 404 "Anomali bulunamadı").
 * Anomaliler ise ML/RCA pipeline'ı tarafından üretilir, frontend'in
 * erişebildiği hiçbir API yüzeyinden doğrudan create edilemez — bu yüzden
 * "gerçek dolu veriyle detay görünümü" ve "closed durum uyarısı" testleri
 * gerçek backend'e çevrilemiyor (CalibrationModal.tsx / AnomalyClusters.tsx
 * ile aynı kısıt — bkz o dosyalardaki doküman notları).
 *
 * Bunun yerine, gerçek backend'in var olmayan bir investigationId için
 * verdiği GERÇEK 404 yanıtını (`{"error":{"code":"HTTP_404","message":
 * "Soruşturma bulunamadı", ...}}`) kapsayan bir hata-yolu testi + saf UI
 * testleri (investigationId=null render etmez, X butonu her koşulda
 * onClose tetikler — bu ikincisi component'in header'ının `isLoading`/
 * `isError` durumundan bağımsız her zaman render edilmesinden dolayı
 * var olmayan bir ID ile de test edilebiliyor) gerçek backend'e karşı
 * çalıştırılıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import type { ReactElement } from "react";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("InvestigationDetailDialog (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let InvestigationDetailDialog: typeof import("../InvestigationDetailDialog").InvestigationDetailDialog;
  let NotificationProvider: typeof import("../../../context/NotificationContext").NotificationProvider;
  let authToken: string;

  // test-utils.tsx'in AllTheProviders'ı NotificationProvider'ı SARMIYOR
  // (bkz test-utils.tsx) — component gerçek `useNotify()` çağırdığı için
  // (mock yok) burada gerçek NotificationProvider ile elle sarmalıyoruz.
  const renderWithNotify = (ui: ReactElement) =>
    render(<NotificationProvider>{ui}</NotificationProvider>);

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor, fireEvent } = await import(
      "../../../test/test-utils"
    ));
    ({ InvestigationDetailDialog } = await import(
      "../InvestigationDetailDialog"
    ));
    ({ NotificationProvider } = await import(
      "../../../context/NotificationContext"
    ));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("investigationId=null ise hiçbir şey render edilmez", () => {
    // NOT: container.firstChild burada kullanılamıyor — gerçek
    // NotificationProvider (mock değil) her koşulda kendi toast
    // container'ını render ediyor. Dialog'a özgü bir elementin (X /
    // "Kapat" butonu) yokluğunu doğruluyoruz.
    renderWithNotify(
      <InvestigationDetailDialog investigationId={null} onClose={() => {}} />,
    );
    expect(screen.queryByLabelText("Kapat")).toBeNull();
  });

  it("var olmayan investigationId için gerçek backend 404 hatası genel hata mesajını gösterir", async () => {
    sessionStorage.setItem("access_token", authToken);
    renderWithNotify(
      <InvestigationDetailDialog investigationId={999999} onClose={() => {}} />,
    );

    expect(screen.getByText("Soruşturma #999999")).toBeInTheDocument();

    await waitFor(
      () => expect(screen.getByText("Güncellenemedi.")).toBeInTheDocument(),
      { timeout: 10000 },
    );
  }, 15000);

  it("X butonu → gerçek backend 404 durumunda dahi onClose tetiklenir", async () => {
    sessionStorage.setItem("access_token", authToken);
    const onClose = vi.fn();
    renderWithNotify(
      <InvestigationDetailDialog investigationId={999999} onClose={onClose} />,
    );

    await waitFor(() =>
      expect(screen.getByText("Soruşturma #999999")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByLabelText("Kapat"));
    expect(onClose).toHaveBeenCalled();
  }, 15000);
});
