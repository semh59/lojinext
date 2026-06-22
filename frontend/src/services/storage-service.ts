/**
 * Tip Güvenli Storage Yönetim Servisi
 *
 * SEC-006: Hassas anahtarlar (access_token) `sessionStorage`'da tutulur —
 * localStorage'daki bir token XSS ile çalınıp kalıcı olurdu. sessionStorage
 * sekme kapanınca temizlenir ve refresh-token (HttpOnly cookie) ile yeni
 * access_token alınır. Diğer (hassas olmayan) anahtarlar localStorage'da
 * kalır (tema, tercihler, filtreler — reload'da korunmalı).
 */

type StorageKey =
  | "access_token"
  | "user_prefs"
  | "theme"
  | "sidebar_state"
  | "last_trip_filters"
  | "dashboard_order"
  | "lojinext-trip-storage"
  | string;

// sessionStorage'a yönlendirilen hassas anahtarlar.
const SESSION_ONLY_KEYS: ReadonlySet<string> = new Set(["access_token"]);

const backendFor = (key: StorageKey): Storage =>
  SESSION_ONLY_KEYS.has(key) ? sessionStorage : localStorage;

export const storageService = {
  /**
   * Veri kaydet
   */
  setItem: <T>(key: StorageKey, value: T): void => {
    try {
      const serializedValue =
        typeof value === "string" ? value : JSON.stringify(value);
      backendFor(key).setItem(key, serializedValue);
      // Hassas anahtarın localStorage'da kalmış eski bir kopyası varsa temizle.
      if (SESSION_ONLY_KEYS.has(key)) {
        localStorage.removeItem(key);
      }
    } catch (error) {
      console.error(`[StorageService] Error saving ${key}:`, error);
    }
  },

  /**
   * Veri oku
   */
  getItem: <T>(key: StorageKey, defaultValue: T | null = null): T | null => {
    try {
      const value = backendFor(key).getItem(key);
      if (value === null) return defaultValue;

      // JSON parse denemesi
      try {
        return JSON.parse(value) as T;
      } catch {
        return value as unknown as T;
      }
    } catch (error) {
      console.error(`[StorageService] Error reading ${key}:`, error);
      return defaultValue;
    }
  },

  /**
   * Veri sil
   */
  removeItem: (key: StorageKey): void => {
    // Her iki backend'den de sil (hassas anahtarların eski kopyaları dahil).
    sessionStorage.removeItem(key);
    localStorage.removeItem(key);
  },

  /**
   * Tümünü temizle (dikkatli kullan)
   */
  clear: (): void => {
    sessionStorage.clear();
    localStorage.clear();
  },

  /**
   * User-scoped key oluştur (B-007 Fix)
   */
  getUserScopedKey: (key: string): string => {
    try {
      const token = sessionStorage.getItem("access_token");
      if (!token) return `${key}-anon`;
      const payload = JSON.parse(atob(token.split(".")[1]));
      const userId = payload.sub || payload.user_id || "anon";
      return `${key}-${userId}`;
    } catch {
      return `${key}-anon`;
    }
  },
};
