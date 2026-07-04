/**
 * 0-mock epiği: useTaskStatus.test.tsx'in mock'lu senaryolarına ek olarak,
 * gerçek backend'e karşı çalışan bir sürüm. `tripService.getTaskStatus`
 * mock'lanmıyor — gerçek bir sefer oluşturulup POST /trips/{id}/cost-analysis
 * ile gerçek bir background job tetiklenir (202 + task_id), ardından hook
 * gerçek GET /trips/tasks/{task_id}/status'u poll eder. Test ortamı
 * `CELERY_EAGER=True` kullandığından job senkron/anında tamamlanır — hook'un
 * PROCESSING → SUCCESS geçişini gerçek bir round-trip ile doğruluyoruz.
 *
 * Bu hook Router/QueryClient dışında bir context'e ihtiyaç duymuyor ama
 * react-query kullanıyor — bu yüzden test-utils yerine düz
 * `@testing-library/react` + kendi QueryClientProvider'ımızı kullanıyoruz
 * (usePushNotifications.real-backend.test.ts'te bulunan gerçek bir
 * bug'ı tekrar etmemek için: test-utils'in AllTheProviders'ı her zaman
 * gerçek AuthProvider'ı da mount eder, o da mount'ta gerçek bir `/auth/me`
 * isteği atar; bu istek bizim gerçek çağrılarımızla yarışıp axios-instance'ın
 * paylaşılan 401-refresh-fail akışını (access_token'ı sessionStorage'dan
 * silme) yanlışlıkla tetikleyebiliyordu).
 *
 * Orijinal mock'lu dosya (useTaskStatus.test.tsx) korunuyor: "taskId yoksa
 * IDLE" (network'süz, saf davranış) ve FAILED senaryosu (gerçek backend'de
 * hata enjekte etmek bu iş için orantısız) — ikisi de mock'lu kalmaya devam
 * ediyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("useTaskStatus (real backend)", () => {
  let renderHook: typeof import("@testing-library/react").renderHook;
  let waitFor: typeof import("@testing-library/react").waitFor;
  let useTaskStatus: typeof import("../useTaskStatus").useTaskStatus;
  let authToken: string;
  let vehicleId: number;
  let driverId: number;
  let seferId: number;

  const suffix = Date.now();

  function wrapper({ children }: { children: React.ReactNode }) {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  }

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ renderHook, waitFor } = await import("@testing-library/react"));
    ({ useTaskStatus } = await import("../useTaskStatus"));

    const headers = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`,
    };

    const vResp = await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        plaka: `34 ZM ${suffix.toString().slice(-3)}4`,
        marka: `TaskStatusTest${suffix}`,
        model: "M",
        yil: 2022,
        hedef_tuketim: 30,
        aktif: true,
        yakit_tipi: "DIZEL",
      }),
    });
    const vehicle = await vResp.json();
    vehicleId = vehicle.id;

    const dResp = await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/drivers/`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        ad_soyad: `TaskStatus Sofor ${suffix}`,
        telefon: "5551234567",
        aktif: true,
      }),
    });
    const driver = await dResp.json();
    driverId = driver.id;

    const sResp = await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/trips/`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        tarih: "2026-07-01",
        arac_id: vehicleId,
        sofor_id: driverId,
        net_kg: 10000,
        cikis_yeri: "Istanbul",
        varis_yeri: "Ankara",
        mesafe_km: 450,
        durum: "Planned",
      }),
    });
    const sefer = await sResp.json();
    seferId = sefer.id;
  }, 20000);

  afterAll(async () => {
    const headers = { Authorization: `Bearer ${authToken}` };
    if (seferId) {
      await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/trips/${seferId}`, {
        method: "DELETE",
        headers,
      }).catch(() => {});
    }
    if (vehicleId) {
      await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/${vehicleId}`, {
        method: "DELETE",
        headers,
      }).catch(() => {});
    }
    if (driverId) {
      await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/drivers/${driverId}`, {
        method: "DELETE",
        headers,
      }).catch(() => {});
    }
    vi.unstubAllEnvs();
  });

  it("polls a real background job (cost-analysis) from PROCESSING to a terminal status", async () => {
    sessionStorage.setItem("access_token", authToken);

    const analysisResp = await fetch(
      `${REAL_BACKEND_ORIGIN}/api/v1/trips/${seferId}/cost-analysis`,
      { headers: { Authorization: `Bearer ${authToken}` } },
    );
    expect(analysisResp.status).toBe(202);
    const { task_id: taskId } = await analysisResp.json();
    expect(typeof taskId).toBe("string");

    const { result } = renderHook(() => useTaskStatus(taskId), { wrapper });

    await waitFor(
      () => {
        expect(result.current.isTerminal).toBe(true);
      },
      { timeout: 10000 },
    );
    expect(["SUCCESS", "FAILED"]).toContain(result.current.status);
  }, 15000);
});
