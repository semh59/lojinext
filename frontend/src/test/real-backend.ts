/**
 * 0-mock epiği Faz 2: gerçek, izole bir backend'e karşı test yardımcıları.
 *
 * Bu dosya `vi.mock` YERİNE gerçek bir backend süreci kullanan testler için
 * ortaktır — `docker compose --profile test up -d api-stub` + izole bir test
 * Postgres'i + host'ta çalışan `uvicorn app.main:app` gerektirir. Backend
 * adresi `REAL_BACKEND_URL` env değişkeninden okunur, varsayılan
 * `http://localhost:8000/api/v1`.
 *
 * Kullanım (test dosyasının en başında, top-level await ile):
 *   const backendUp = await isRealBackendReachable();
 *   describe.skipIf(!backendUp)("locationService (real backend)", () => { ... });
 *
 * Backend erişilemezse (ör. bu makinede/CI adımında henüz kurulu değilse)
 * suit sessizce SKIP edilir, FAIL değil — böylece backend'siz bir ortamda
 * çalıştırılırsa geri kalan suit'i kırmaz.
 */
import axios from "axios";
import { existsSync, readFileSync, writeFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

// Token cache dosya-seviyesinde, AYRI `npx vitest` process çağrıları arasında
// paylaşılır — backend'in /auth/token endpoint'i gerçek brute-force
// koruması ile rate-limited (prod ile aynı); iteratif lokal geliştirmede her
// test dosyası çalıştırmasında yeniden login olmak bu limiti gereksiz yere
// tüketiyordu (CI'da her dosya zaten sadece BİR kez login olur). 10 dakika
// TTL, access token'ın kendi ömrünün rahatça içinde.
const TOKEN_CACHE_FILE = join(tmpdir(), "lojinext_faz2_test_token.json");
const TOKEN_CACHE_TTL_MS = 10 * 60 * 1000;

// NOT: orval'ın ürettiği client path'leri zaten "/api/v1/..." prefix'ini
// içeriyor (bkz generated/api/*/*.ts, url: `/api/v1/locations/` gibi) —
// bu yüzden VITE_API_URL SADECE origin olmalı, "/api/v1" eklenmemeli
// (aksi halde axios-instance.ts'in baseURL'i ile path'ler çakışıp
// "/api/v1/api/v1/..." gibi çift-prefiksli, hep 404 dönen bir URL üretir).
export const REAL_BACKEND_ORIGIN =
  process.env.REAL_BACKEND_URL || "http://localhost:8000";
export const REAL_BACKEND_URL = `${REAL_BACKEND_ORIGIN}/api/v1`;

let cachedReachable: boolean | null = null;
let cachedToken: string | null = null;

// Tek 2s'lik denemeyle karar vermek transient bir gecikmeyi (backend soğuk
// başlangıçta health probe'a hemen cevap veremiyorsa, ya da Docker
// host'unda anlık bir CPU/IO tepesi varsa) "erişilemez" ile karıştırıp
// TÜM real-backend suite'lerini sessizce SKIP'letebilir — CI'da açıklaması
// zor, flaky bir coverage düşüşü olarak görünür (diğer ajanın bulgusu).
// 3 deneme × 2s timeout, aralarda ~500ms bekleme; ilk başarıda hemen true
// döner. Davranış aynı kalıyor: gerçekten erişilemezse yine false + aynı
// console.warn (suit'i FAIL değil SKIP eder).
const REACHABILITY_ATTEMPTS = 3;
const REACHABILITY_RETRY_DELAY_MS = 500;

export async function isRealBackendReachable(): Promise<boolean> {
  if (cachedReachable !== null) return cachedReachable;

  for (let attempt = 1; attempt <= REACHABILITY_ATTEMPTS; attempt += 1) {
    try {
      await axios.get(`${REAL_BACKEND_URL}/health/`, { timeout: 2000 });
      cachedReachable = true;
      return cachedReachable;
    } catch {
      if (attempt < REACHABILITY_ATTEMPTS) {
        await new Promise((resolve) =>
          setTimeout(resolve, REACHABILITY_RETRY_DELAY_MS),
        );
      }
    }
  }

  cachedReachable = false;
  console.warn(
    `[real-backend] ${REAL_BACKEND_URL} erişilemez — bu suit atlanacak.`,
  );
  return cachedReachable;
}

function readCachedTokenFromDisk(): string | null {
  if (!existsSync(TOKEN_CACHE_FILE)) return null;
  try {
    const cached = JSON.parse(readFileSync(TOKEN_CACHE_FILE, "utf-8")) as {
      token: string;
      ts: number;
    };
    if (Date.now() - cached.ts < TOKEN_CACHE_TTL_MS) {
      return cached.token;
    }
  } catch {
    // Bozuk/eksik cache dosyası — normal login akışına düş.
  }
  return null;
}

/** Gerçek `POST /auth/token` çağrısı yapar; 429'da diğer worker'ların
 * yazdığı disk cache'i kontrol ederek (double-checked locking) veya kısa
 * bir bekleme sonrası tek retry ile toparlanır. `writeCache=true` ise
 * sonucu paylaşılan disk cache'ine yazar (bkz loginAsAdmin); `false` ise
 * YAZMAZ — bu, sonucu invalidate edecek (ör. logout/blacklist) bir teste
 * özel, paylaşılmayan bir token almak için kullanılır (bkz
 * loginFreshUncached).
 */
async function loginRaw(writeCache: boolean): Promise<string> {
  const params = new URLSearchParams();
  params.set("username", process.env.REAL_BACKEND_ADMIN_USER || "admin");
  params.set(
    "password",
    process.env.REAL_BACKEND_ADMIN_PASSWORD || "faz2_test_admin_pw",
  );

  const MAX_ATTEMPTS = 3;
  let lastErr: unknown;
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
    try {
      const resp = await axios.post(`${REAL_BACKEND_URL}/auth/token`, params, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      const token = resp.data.access_token as string;
      if (writeCache) {
        cachedToken = token;
        writeFileSync(
          TOKEN_CACHE_FILE,
          JSON.stringify({ token, ts: Date.now() }),
        );
      }
      return token;
    } catch (err) {
      lastErr = err;
      const status = (err as { response?: { status?: number } })?.response
        ?.status;
      if (status !== 429 || attempt === MAX_ATTEMPTS) throw err;

      if (writeCache) {
        // Another worker may have just won the race and written the cache —
        // check before burning another retry against the same bucket.
        const wonByOther = readCachedTokenFromDisk();
        if (wonByOther) {
          cachedToken = wonByOther;
          return cachedToken;
        }
      }

      const retryAfterHeader = (
        err as { response?: { headers?: Record<string, string> } }
      )?.response?.headers?.["retry-after"];
      const retryAfterMs = retryAfterHeader
        ? Number(retryAfterHeader) * 1000
        : 1500;
      await new Promise((resolve) =>
        setTimeout(resolve, Math.min(retryAfterMs, 5000)),
      );

      if (writeCache) {
        const wonWhileWaiting = readCachedTokenFromDisk();
        if (wonWhileWaiting) {
          cachedToken = wonWhileWaiting;
          return cachedToken;
        }
      }
    }
  }
  throw lastErr;
}

/** Gerçek backend'e karşı superadmin login yapar, access_token döner
 * (in-process + disk cache'li — bkz TOKEN_CACHE_FILE docstring'i).
 *
 * Vitest varsayılan olarak her test dosyasını AYRI bir worker process'te
 * paralel çalıştırır — her worker'ın kendi module-level `cachedToken`'ı boş
 * başlar. Birden fazla real-backend dosyası aynı anda `beforeAll`'da bu
 * fonksiyonu çağırdığında (ör. bu dilimdeki 4 dosya birlikte koşulunca),
 * disk cache dosyası henüz yazılmamışsa hepsi AYNI ANDA gerçek
 * `POST /auth/token`'a gidiyor — backend'in süper-admin login'i için çok
 * sıkı IP-scoped rate limiti (3 istek / 300 sn, brute-force koruması,
 * app/api/v1/endpoints/auth.py) bu "thundering herd" ile anında tükeniyor
 * ve 429 dönüyor (ampirik olarak bu dilimdeki 4 dosya birlikte koşulunca
 * gözlendi). Çift-kontrollü kilitleme: 429 alınca disk cache'i tekrar
 * oku — yarışı kazanan başka bir worker onu az önce yazmış olabilir; hâlâ
 * yoksa `Retry-After` kadar (veya kısa bir varsayılan) bekleyip bir kez
 * daha dene.
 *
 * UYARI: bu paylaşılan (disk-cache'li) token'ı ASLA invalidate eden bir
 * çağrıda (ör. `/auth/logout`, ki bu token'ı sunucu tarafında blacklist'e
 * ekler) kullanma — aynı anda koşan BAŞKA bir dosya da bu cache'ten aynı
 * token'ı okuyup kullanıyor olabilir, ve onu blacklist'lemek o dosyayı
 * ortasında 401'e düşürür (ampirik olarak bu dilimdeki 4 dosya birlikte
 * koşulunca gözlendi — AuthContext'in logout testi cache'i paylaşan başka
 * bir dosyayı 401'e düşürüyordu). Böyle testler için `loginFreshUncached()`
 * kullan.
 */
export async function loginAsAdmin(): Promise<string> {
  if (cachedToken) return cachedToken;

  const fromDisk = readCachedTokenFromDisk();
  if (fromDisk) {
    cachedToken = fromDisk;
    return cachedToken;
  }

  return loginRaw(true);
}

/** `loginAsAdmin()`'in aksine paylaşılan disk cache'i HİÇ okumaz/yazmaz —
 * her zaman taze, bu çağrıya ÖZEL bir token döner. Sadece token'ı
 * invalidate edecek (logout/blacklist gibi) senaryolarda kullan; aksi
 * halde gereksiz yere kıt süper-admin login bucket'ını tüketir (bkz
 * loginAsAdmin docstring'i — 3 istek / 300 sn). */
export async function loginFreshUncached(): Promise<string> {
  return loginRaw(false);
}
