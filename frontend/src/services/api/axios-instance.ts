import axios, {
  AxiosInstance,
  AxiosError,
  InternalAxiosRequestConfig,
} from "axios";
import { toast } from "sonner";
import { storageService } from "../storage-service";
import { errorTracker } from "../error-tracker";
import i18n from "../../i18n";

interface ApiErrorResponse {
  error?: { code: string; message: string; trace_id?: string };
  detail?: string | Array<{ msg: string; loc: string[] }>;
  message?: string;
}

declare module "axios" {
  export interface InternalAxiosRequestConfig {
    _retry?: boolean;
  }
}

const API_BASE_URL = import.meta.env.VITE_API_URL || "/api/v1";

// Refresh mutex: prevents N concurrent 401s from firing N /auth/refresh calls.
let isRefreshing = false;
type QueueEntry = {
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
};
let refreshQueue: QueueEntry[] = [];

function processRefreshQueue(
  error: unknown,
  token: string | null = null,
): void {
  refreshQueue.forEach((entry) => {
    if (error) entry.reject(error);
    else entry.resolve(token!);
  });
  refreshQueue = [];
}

const axiosInstance: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request Interceptor: access_token header
axiosInstance.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = storageService.getItem<string>("access_token");
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: unknown) => Promise.reject(error),
);

// Response Interceptor
axiosInstance.interceptors.response.use(
  (response) => {
    // Capture backend trace_id for correlation on successful responses
    const traceId = response.headers["x-correlation-id"] as string | undefined;
    if (traceId) errorTracker.setLastTraceId(traceId);
    return response;
  },
  async (error: AxiosError) => {
    const originalRequest = error.config;

    if (error.response) {
      const { status, data } = error.response;

      // 401: refresh_token cookie ile yeni access_token al
      if (status === 401 && !originalRequest?.url?.includes("/auth/token")) {
        if (originalRequest?._retry) {
          // Retry after refresh still 401 → hard logout
          storageService.removeItem("access_token");
          if (window.location.pathname !== "/login")
            window.location.href = "/login";
          return Promise.reject(
            new Error(
              i18n.t(
                "auth.session_expired",
                "Session expired, please log in again.",
              ),
            ),
          );
        }

        if (isRefreshing) {
          // Queue this request until the in-flight refresh completes
          return new Promise<string>((resolve, reject) => {
            refreshQueue.push({ resolve, reject });
          }).then((token) => {
            if (originalRequest?.headers)
              originalRequest.headers.Authorization = `Bearer ${token}`;
            return axiosInstance(originalRequest!);
          });
        }

        if (originalRequest) originalRequest._retry = true;
        isRefreshing = true;

        try {
          const resp = await axios.post(
            `${API_BASE_URL}/auth/refresh`,
            {},
            { withCredentials: true },
          );
          const { access_token } = resp.data as { access_token: string };
          storageService.setItem("access_token", access_token);
          processRefreshQueue(null, access_token);
          if (originalRequest?.headers) {
            originalRequest.headers.Authorization = `Bearer ${access_token}`;
            return axiosInstance(originalRequest);
          }
        } catch (refreshError) {
          processRefreshQueue(refreshError);
          storageService.removeItem("access_token");
          if (window.location.pathname !== "/login")
            window.location.href = "/login";
          return Promise.reject(
            new Error(
              i18n.t(
                "auth.session_expired",
                "Session expired, please log in again.",
              ),
            ),
          );
        } finally {
          isRefreshing = false;
        }
      }

      if (status === 403) {
        toast.error(
          i18n.t(
            "errors.forbidden",
            "You do not have permission to perform this action.",
          ),
        );
      }

      if (status === 400) {
        const errData = data as ApiErrorResponse;
        const message =
          errData?.error?.message ??
          (typeof errData?.detail === "string" ? errData.detail : undefined) ??
          i18n.t("errors.invalid_operation", "Invalid operation");
        toast.error(message);
      }

      if (status === 422) {
        const errData = data as ApiErrorResponse;
        if (errData?.error?.message) {
          toast.error(errData.error.message);
        } else if (Array.isArray(errData?.detail)) {
          toast.error(
            (errData.detail as Array<{ msg: string }>)[0]?.msg ||
              i18n.t("errors.invalid_input", "Invalid data input"),
          );
        } else {
          toast.error(
            (typeof errData?.detail === "string" ? errData.detail : null) ??
              i18n.t("errors.validation_error", "Validation error"),
          );
        }
      }

      if (status === 429) {
        const errData = data as ApiErrorResponse;
        const message =
          errData?.error?.message ??
          (typeof errData?.detail === "string" ? errData.detail : undefined) ??
          i18n.t(
            "errors.rate_limited",
            "Too many requests. Please slow down and try again shortly.",
          );
        toast.error(message);
      }

      if (status >= 500) {
        toast.error(
          i18n.t(
            "errors.server_error",
            "A server error occurred. Please try again later.",
          ),
        );
      }

      // Report all non-2xx to error tracker (4xx handled with lower severity)
      const traceId = error.response?.headers?.["x-correlation-id"] as
        | string
        | undefined;
      const path = originalRequest?.url ?? "unknown";
      const errorCode = (data as ApiErrorResponse)?.error?.code;
      const severity: "fatal" | "error" | "warning" =
        status >= 500
          ? "error"
          : status === 401
            ? "warning"
            : status === 403
              ? "warning"
              : "warning";
      errorTracker.captureApiError({
        status,
        path,
        traceId,
        severity,
        errorCode,
      });
    } else if (error.request) {
      toast.error(
        i18n.t(
          "errors.network_error",
          "Cannot reach server. Please check your internet connection.",
        ),
      );
      errorTracker.captureApiError({
        severity: "fatal",
        path: error.config?.url ?? "unknown",
        traceId: errorTracker.getLastTraceId(),
      });
    }

    return Promise.reject(error);
  },
);

export default axiosInstance;
