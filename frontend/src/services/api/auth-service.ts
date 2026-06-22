import axiosInstance from "./axios-instance";
import { storageService } from "../storage-service";
import { validateResponse } from "../../lib/api-validator";
import { LoginResponseSchema, MeResponseSchema } from "../../schemas/services";

const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

export const tokenStorage = {
  get: () => storageService.getItem<string>("access_token"),
  set: (accessToken: string) => {
    storageService.setItem("access_token", accessToken);
  },
  remove: () => {
    storageService.removeItem("access_token");
  },
  clear: () => {
    storageService.removeItem("access_token");
  },
};

// fetchWithAuth is kept only for unauthenticated auth endpoints (login form,
// password-reset) where axiosInstance's 401 interceptor must not fire.
async function _doFetch(
  url: string,
  options: RequestInit,
  token: string | null,
): Promise<Response> {
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(`${API_BASE}${url}`, {
    ...options,
    headers,
    credentials: "include",
  });
}

function _extractErrorMessage(response: Response, errorData: unknown): string {
  if (typeof errorData === "object" && errorData !== null) {
    const d = errorData as Record<string, unknown>;
    if (typeof d.detail === "string") return d.detail;
    if (Array.isArray(d.detail) && (d.detail[0] as Record<string, string>)?.msg)
      return (d.detail[0] as Record<string, string>).msg;
    if (typeof d.message === "string") return d.message;
    if (d.detail) return JSON.stringify(d.detail);
  }
  return response.statusText;
}

export async function fetchWithAuth(
  url: string,
  options: RequestInit = {},
): Promise<Response> {
  const token = tokenStorage.get();
  const response = await _doFetch(url, options, token);

  if (!response.ok) {
    let errorData: unknown;
    try {
      errorData = await response.clone().json();
    } catch {
      /* JSON değil */
    }
    throw new Error(_extractErrorMessage(response, errorData));
  }

  return response;
}

export const authApi = {
  login: async (username: string, password: string) => {
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);

    const response = await fetch(`${API_BASE}/auth/token`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formData,
    });

    if (!response.ok) {
      if (response.status === 401)
        throw new Error("Kullanıcı adı veya şifre hatalı");
      throw new Error("Giriş yapılamadı");
    }

    const data = await response.json();
    return validateResponse(LoginResponseSchema, data, "authApi.login");
  },

  getMe: async () => {
    const { data } = await axiosInstance.get("/auth/me");
    return validateResponse(MeResponseSchema, data, "authApi.getMe");
  },

  logout: async () => {
    try {
      await axiosInstance.post("/auth/logout");
    } catch (error) {
      console.error("Backend logout failed:", error);
    }
  },
};
