/**
 * 0-mock epiği: ReceiptUpload'ın gerçek backend'e karşı senaryoları.
 *
 * `fuelService.ocrPreview` gerçek `POST /api/v1/fuel/ocr-preview` endpoint'ine
 * gider; bu endpoint dosyayı ayrı bir mikroservise (`ocr_service`, gerçek
 * easyocr) proxy'ler (bkz app/api/v1/endpoints/fuel.py:199). Bu servis bu
 * ortamda gerçekten ayakta (`lojinext-ocr-service-1`, healthy).
 *
 * OCR'ın gerçek bir fiş fotoğrafından "45.5 LT" / "PETROL OFISI" gibi tam
 * metinleri güvenilir biçimde çıkarması deterministik değil (gerçek bir
 * görüntüden gerçek karakter tanıma) — bu yüzden içerik-spesifik OCR
 * asserion'ları (`45.5`, `PETROL OFISI`) mock'lu orijinal dosyada kalıyor.
 * Burada test edilen, gerçek HTTP round-trip'in DOĞRU DAVRANDIĞI iki gerçek
 * yol: (1) geçerli bir görsel (1x1 PNG) yüklenince gerçek OCR servisinden
 * dönen (boş görüntü için) tüm-null yapılandırılmış alanlarla form render
 * ediliyor ve onConfirm bu (null) alanlarla çağrılıyor, (2) gerçekten
 * çok kısa/magic-byte doğrulamasını geçemeyen bir dosya gerçek 415 döndürüyor
 * ve component bunu `fuel.ocr_error` mesajıyla gösteriyor (bkz
 * app/api/v1/endpoints/internal.py:57 `_looks_like_allowed_image` — 12
 * byte'tan kısa veya imza uyuşmayan içerik reddedilir).
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

// Minimal valid 1x1 transparent PNG (magic bytes + a real, decodable image) —
// long enough (>12 bytes) to pass `_looks_like_allowed_image`, and a genuine
// image so the real OCR service can process it without erroring (it will
// simply find no text, since the image is blank).
const TINY_PNG_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";

function tinyPngFile(name = "fis.png"): File {
  const bytes = Uint8Array.from(atob(TINY_PNG_BASE64), (c) => c.charCodeAt(0));
  return new File([bytes], name, { type: "image/png" });
}

describe.skipIf(!backendUp)("ReceiptUpload (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let ReceiptUpload: typeof import("../ReceiptUpload").ReceiptUpload;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, fireEvent } = await import("../../../test/test-utils"));
    ({ ReceiptUpload } = await import("../ReceiptUpload"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("valid görsel yüklenince gerçek OCR round-trip sonrası form alanları render edilir", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<ReceiptUpload onConfirm={vi.fn()} />);

    const input = screen.getByLabelText(/fiş yükle/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [tinyPngFile()] } });

    // Boş görüntüde OCR hiçbir metin bulamaz -> tüm alanlar null -> input
    // value="" olarak render edilir. "Onayla" butonunun görünmesi, gerçek
    // backend'den `fields` state'inin dolduğunu (hata değil, başarı yolunu)
    // kanıtlar.
    const confirmBtn = await screen.findByText(
      "Onayla",
      {},
      { timeout: 15000 },
    );
    expect(confirmBtn).toBeInTheDocument();
    expect(screen.getByText("İstasyon")).toBeInTheDocument();
    expect(screen.getByText("Litre")).toBeInTheDocument();
  }, 20000);

  it("onConfirm'i gerçek backend'den dönen (boş görüntü için null) alanlarla çağırır", async () => {
    const onConfirm = vi.fn();
    sessionStorage.setItem("access_token", authToken);
    render(<ReceiptUpload onConfirm={onConfirm} />);

    fireEvent.change(screen.getByLabelText(/fiş yükle/i), {
      target: { files: [tinyPngFile()] },
    });

    const btn = await screen.findByText("Onayla", {}, { timeout: 15000 });
    fireEvent.click(btn);

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({ istasyon: null, litre: null }),
    );
  }, 20000);

  it("geçersiz (çok kısa) dosya gerçek 415 döner, hata mesajı gösterilir", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<ReceiptUpload onConfirm={vi.fn()} />);

    // 3 byte'lık dosya `_looks_like_allowed_image`'in 12-byte alt sınırını
    // geçemez -> backend 415 -> component generic hata mesajını gösterir.
    const shortFile = new File(
      [new Uint8Array([0xff, 0xd8, 0xff])],
      "fis.jpg",
      {
        type: "image/jpeg",
      },
    );
    fireEvent.change(screen.getByLabelText(/fiş yükle/i), {
      target: { files: [shortFile] },
    });

    expect(
      await screen.findByText(
        "OCR okunamadı; alanları elle girebilirsiniz.",
        {},
        { timeout: 15000 },
      ),
    ).toBeInTheDocument();
  }, 20000);
});
