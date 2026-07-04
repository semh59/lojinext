/**
 * 0-mock epiği: ImportProgressModal.test.tsx'in mock'lu senaryolarına ek
 * olarak, gerçek backend'e karşı iki senaryo. Bu bileşen `app/api/v1`'in
 * async-job pattern'ini uçtan uca kullanır (bkz CLAUDE.md "Async job
 * pattern"): `POST /trips/upload?async_mode=true` bir `task_id` döner,
 * `useTaskStatus` gerçek `GET /trips/tasks/{task_id}/status`'u 1500ms
 * aralıkla poll eder — burada her iki uç da mock'lanmadan gerçek HTTP
 * round-trip ile doğrulanıyor.
 *
 * Test 1: Excel olmayan bir dosya -> backend 400 döner (curl ile
 * doğrulandı: `{"error":{"code":"HTTP_400","message":"Sadece Excel
 * dosyalari (.xlsx, .xls) kabul edilir."}}`) -> component'in
 * `err.response.data.error.message` okuma yolu gerçek zarfla eşleşiyor mu.
 *
 * Test 2: Yalnızca başlık satırı olan (veri satırı olmayan) gerçek bir
 * .xlsx -> job PROCESSING'den SUCCESS'e geçer (`success:false,
 * total_rows:1, success_count:0, failed_count:1`, curl ile doğrulandı) ->
 * component "Tamamlandı: 0 satır işlendi, 1 satır atlandı." ve hata
 * detayını gösteriyor mu.
 */
import { beforeAll, afterAll, describe, expect, it, vi } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";

// Sadece "Plaka" başlık satırı içeren, veri satırı olmayan minimal bir
// .xlsx (openpyxl ile üretildi) — gerçek backend'in
// "Excel dosyasinda gecerli veri bulunamadi" satır-hatasını tetikler.
// pragma: allowlist secret
const EMPTY_TRIPS_XLSX_BASE64 =
  "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"; // pragma: allowlist secret

function base64ToUint8Array(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function emptyTripsXlsxFile(): File {
  return new File(
    [base64ToUint8Array(EMPTY_TRIPS_XLSX_BASE64).buffer as ArrayBuffer],
    "trips.xlsx",
    {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
  );
}

function notExcelFile(): File {
  return new File(["hello"], "notexcel.txt", { type: "text/plain" });
}

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("ImportProgressModal (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let ImportProgressModal: typeof import("../ImportProgressModal").ImportProgressModal;
  let authToken: string;

  beforeAll(async () => {
    // ImportProgressModal -> tripService.uploadExcelAsync raw axiosInstance
    // ile "/trips/upload" gibi "/api/v1" ÖNEKSİZ path'ler kullanıyor (bkz
    // src/api/trips.ts) — origin-only VITE_API_URL (diğer real-backend
    // dosyalarının çoğunun kullandığı convention) bu path'leri 404'e
    // düşürür. getTaskStatus ise orval-üretilen client'ı kullanıyor (path
    // zaten "/api/v1/..." önekli); orval-mutator.ts'teki
    // stripDuplicateApiPrefix, baseURL "/api/v1" ile bitince bu çifte-öneki
    // otomatik temizliyor. Bu yüzden REAL_BACKEND_URL (origin+"/api/v1")
    // her iki çağrı şeklini de doğru çözüyor — curl ile doğrulandı.
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ ImportProgressModal } = await import("../ImportProgressModal"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("Excel olmayan dosya gerçek backend'den 400 döner, gerçek hata mesajı gösterilir", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<ImportProgressModal file={notExcelFile()} onClose={vi.fn()} />);

    await waitFor(
      () =>
        expect(
          screen.getByText(
            "Sadece Excel dosyalari (.xlsx, .xls) kabul edilir.",
          ),
        ).toBeInTheDocument(),
      { timeout: 10000 },
    );
  }, 15000);

  it("veri satırı olmayan gerçek Excel yüklenince job SUCCESS'e geçer ve satır-hatası özetini gösterir", async () => {
    sessionStorage.setItem("access_token", authToken);
    const onComplete = vi.fn();
    render(
      <ImportProgressModal
        file={emptyTripsXlsxFile()}
        onClose={vi.fn()}
        onComplete={onComplete}
      />,
    );

    // PROCESSING -> gerçek backend job'ı işleyip SUCCESS'e (satır
    // seviyesinde başarısız) geçene kadar gerçek polling ile bekle.
    await waitFor(
      () =>
        expect(
          screen.getByText("Tamamlandı: 0 satır işlendi, 1 satır atlandı."),
        ).toBeInTheDocument(),
      { timeout: 20000 },
    );

    expect(screen.getByText("İlk 1 hata (1 toplam)")).toBeInTheDocument();
    expect(onComplete).toHaveBeenCalled();
  }, 25000);
});
