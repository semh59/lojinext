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

export async function isRealBackendReachable(): Promise<boolean> {
  if (cachedReachable !== null) return cachedReachable;
  try {
    await axios.get(`${REAL_BACKEND_URL}/health/`, { timeout: 2000 });
    cachedReachable = true;
  } catch {
    cachedReachable = false;
    console.warn(
      `[real-backend] ${REAL_BACKEND_URL} erişilemez — bu suit atlanacak.`,
    );
  }
  return cachedReachable;
}

/** Gerçek backend'e karşı superadmin login yapar, access_token döner
 * (in-process + disk cache'li — bkz TOKEN_CACHE_FILE docstring'i). */
export async function loginAsAdmin(): Promise<string> {
  if (cachedToken) return cachedToken;

  if (existsSync(TOKEN_CACHE_FILE)) {
    try {
      const cached = JSON.parse(readFileSync(TOKEN_CACHE_FILE, "utf-8")) as {
        token: string;
        ts: number;
      };
      if (Date.now() - cached.ts < TOKEN_CACHE_TTL_MS) {
        cachedToken = cached.token;
        return cachedToken;
      }
    } catch {
      // Bozuk/eksik cache dosyası — normal login akışına düş.
    }
  }

  const params = new URLSearchParams();
  params.set("username", process.env.REAL_BACKEND_ADMIN_USER || "admin");
  params.set(
    "password",
    process.env.REAL_BACKEND_ADMIN_PASSWORD || "faz2_test_admin_pw",
  );
  const resp = await axios.post(`${REAL_BACKEND_URL}/auth/token`, params, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  cachedToken = resp.data.access_token as string;
  writeFileSync(
    TOKEN_CACHE_FILE,
    JSON.stringify({ token: cachedToken, ts: Date.now() }),
  );
  return cachedToken;
}
