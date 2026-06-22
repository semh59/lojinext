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

export const customAxiosInstance = <T>(
  config: AxiosRequestConfig,
  options?: { signal?: AbortSignal },
): Promise<T> =>
  axiosInstance<T>({
    ...config,
    signal: options?.signal,
  }).then(({ data }) => data);
