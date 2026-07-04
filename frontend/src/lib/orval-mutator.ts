// Orval custom mutator — mevcut axiosInstance'ı wrap eder.
//
// Token refresh, 401/403/400/422/500 handling, errorTracker, trace_id capture
// hepsi src/services/api/axios-instance.ts interceptor'larında yaşar.
// Bu dosya yalnızca orval'ın beklediği imzayı sağlar:
//   customAxiosInstance<T>(config, options?) → Promise<T>
//
// Orval şu şekilde çağırır:
//   const data = await customAxiosInstance<SeferResponse>({ url, method, params })
// axiosInstance ise { data: T } şeklinde yanıt verir; bu wrapper sadece .data alır.

import type { AxiosRequestConfig } from "axios";
import axiosInstance from "../services/api/axios-instance";

// Orval-generated request configs always embed the full "/api/v1/..." path
// themselves (see generated/api/*/*.ts, e.g. `url: \`/api/v1/vehicles/\``).
// axiosInstance's baseURL is independently configurable via VITE_API_URL and
// in the shipped production build (docker-compose.yml / CI both bake
// VITE_API_URL=/api/v1) it ALSO already carries "/api/v1". When both carry
// the prefix, the concatenated request URL doubles to
// "/api/v1/api/v1/vehicles/" and 404s — silently breaking every page built
// on a generated client (vehicles, drivers, fuel, ...) whenever
// axiosInstance's baseURL happens to include "/api/v1" (verified against the
// real backend: GET /api/v1/vehicles/ -> 200, GET /api/v1/api/v1/vehicles/
// -> 404). Strip the duplicate segment here so callers work regardless of
// which baseURL convention (origin-only vs origin+/api/v1) is configured.
const stripDuplicateApiPrefix = (
  url: string | undefined,
): string | undefined => {
  if (!url) return url;
  const base = axiosInstance.defaults.baseURL ?? "";
  if (/\/api\/v1\/?$/.test(base) && url.startsWith("/api/v1")) {
    return url.slice("/api/v1".length) || "/";
  }
  return url;
};

export const customAxiosInstance = <T>(
  config: AxiosRequestConfig,
  options?: { signal?: AbortSignal },
): Promise<T> =>
  axiosInstance<T>({
    ...config,
    url: stripDuplicateApiPrefix(config.url),
    signal: options?.signal,
  }).then(({ data }) => data);
