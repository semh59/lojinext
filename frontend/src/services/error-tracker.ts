/**
 * Unified frontend error tracker.
 * - captureApiError: axios 4xx/5xx with trace_id correlation
 * - capture: JS errors, component stack, React boundary
 * - captureMessage: console.error, Web Vitals, resource failures
 * - sendBeacon flush: ensures errors on pagehide are delivered
 *
 * NOTE: _sendReport uses fetch (not axiosInstance) to avoid infinite loop
 * when the /system/error-report endpoint itself fails (the axios interceptor
 * calls captureApiError which would re-trigger _sendReport endlessly).
 */

import { storageService } from "./storage-service";

export interface ErrorReport {
  message: string;
  stack?: string;
  componentStack?: string;
  url: string;
  userAgent: string;
  timestamp: string;
  severity: "error" | "warning" | "fatal";
  backend_trace_id?: string;
  frontend_session_id: string;
  extra?: Record<string, unknown>;
}

export interface ApiErrorReport {
  status?: number;
  path: string;
  traceId?: string;
  severity: ErrorReport["severity"];
  errorCode?: string;
  extra?: Record<string, unknown>;
}

class ErrorTracker {
  private readonly sessionId: string;
  private lastTraceId: string = "";
  /**
   * Combined map for dedup tracking.
   * key → { ts: last_report_ms, count: report_count }
   *
   * For API errors: key = "API <status> <path>:[stackSig]"
   * stack is explicitly undefined for captureApiError so stackSig='',
   * making the key = "API 500 /path:" — same path+status always deduplicates,
   * different status codes produce different keys. This is intentional.
   */
  private reportedErrors = new Map<string, { ts: number; count: number }>();
  private pendingReports: ErrorReport[] = [];
  private readonly MAX_REPORTS_PER_KEY = 3;
  private readonly COOLDOWN_MS = 60_000;
  private readonly MAX_PENDING = 50;

  constructor() {
    this.sessionId = this._generateSessionId();
  }

  private _generateSessionId(): string {
    return `${Date.now().toString(36)}-${Math.random()
      .toString(36)
      .slice(2, 8)}`;
  }

  // ── Public API ──────────────────────────────────────────────────────────

  /** Called by axios interceptor for all non-2xx responses. */
  captureApiError(report: ApiErrorReport): void {
    const message = [
      `API ${report.status ?? "NETWORK"} ${report.path}`,
      report.errorCode ? `[${report.errorCode}]` : "",
    ]
      .filter(Boolean)
      .join(" ");

    this.capture(Object.assign(new Error(message), { stack: undefined }), {
      severity: report.severity,
      extra: {
        status: report.status,
        path: report.path,
        error_code: report.errorCode,
        ...report.extra,
      },
      traceId: report.traceId,
    });
  }

  /** Capture an Error object (from ErrorBoundary, window.onerror, etc.). */
  capture(
    error: Error,
    extra?: {
      componentStack?: string;
      severity?: ErrorReport["severity"];
      extra?: Record<string, unknown>;
      traceId?: string;
    },
  ): void {
    // Normalize the stack to the first meaningful line to improve dedup accuracy.
    // Raw stacks include line numbers that differ across hot-reload sessions.
    const stackSig =
      error.stack
        ?.split("\n")
        .slice(0, 3)
        .map((l) => l.replace(/:\d+:\d+/g, "")) // strip line:col numbers
        .join("|")
        .slice(0, 150) ?? "";
    const key = `${error.message}:${stackSig}`;
    const now = Date.now();
    const entry = this.reportedErrors.get(key);
    const lastReport = entry?.ts ?? 0;

    if (now - lastReport < this.COOLDOWN_MS) return;

    const count = entry?.count ?? 0;
    if (count >= this.MAX_REPORTS_PER_KEY) return;

    this.reportedErrors.set(key, { ts: now, count: count + 1 });

    // Evict entries older than 2×COOLDOWN to prevent unbounded growth in long sessions
    if (this.reportedErrors.size > 500) {
      const cutoff = now - 2 * this.COOLDOWN_MS;
      for (const [k, rec] of this.reportedErrors) {
        if (rec.ts < cutoff) {
          this.reportedErrors.delete(k);
        }
      }
    }

    const report: ErrorReport = {
      message: error.message,
      stack: error.stack,
      componentStack: extra?.componentStack,
      url: window.location.href,
      userAgent: navigator.userAgent,
      timestamp: new Date().toISOString(),
      severity: extra?.severity ?? "error",
      backend_trace_id: extra?.traceId ?? this.lastTraceId ?? undefined,
      frontend_session_id: this.sessionId,
      extra: extra?.extra,
    };

    this._enqueue(report);
  }

  /** Capture a plain message (Web Vitals, console.error, resource failures). */
  captureMessage(
    message: string,
    severity: ErrorReport["severity"] = "warning",
    extra?: Record<string, unknown>,
  ): void {
    this.capture(new Error(message), { severity, extra });
  }

  /** Called by axios interceptor to store the last seen correlation ID. */
  setLastTraceId(traceId: string): void {
    this.lastTraceId = traceId;
  }

  getLastTraceId(): string {
    return this.lastTraceId;
  }

  /** Install global window listeners. Call once in main.tsx. */
  install(): void {
    window.addEventListener("error", (event) => {
      if (event.error) this.capture(event.error, { severity: "error" });
    });

    window.addEventListener("unhandledrejection", (event) => {
      const error =
        event.reason instanceof Error
          ? event.reason
          : new Error(String(event.reason));
      this.capture(error, { severity: "warning" });
    });

    // Flush pending reports on page unload (sendBeacon guarantees delivery)
    window.addEventListener("pagehide", () => {
      this._flushBeacon();
    });
  }

  /** Flush pending reports (exposed for testing). */
  flushPending(): ErrorReport[] {
    return this.pendingReports.splice(0);
  }

  reset(): void {
    this.reportedErrors.clear();
    this.pendingReports = [];
  }

  // ── Internal ────────────────────────────────────────────────────────────

  private _enqueue(report: ErrorReport): void {
    // Always attempt immediate send; beacon only picks up what's left in pending
    void this._sendReport(report);
    // Add to pending so beacon can retry if _sendReport hasn't resolved yet
    if (this.pendingReports.length < this.MAX_PENDING) {
      this.pendingReports.push(report);
    }
  }

  private _flushBeacon(): void {
    const pending = this.flushPending();
    if (pending.length === 0) return;
    // Chunk to avoid exceeding the 64KB sendBeacon payload limit
    const CHUNK = 20;
    for (let i = 0; i < pending.length; i += CHUNK) {
      const chunk = pending.slice(i, i + CHUNK);
      navigator.sendBeacon(
        "/api/v1/system/error-report-batch",
        JSON.stringify(chunk),
      );
    }
  }

  private async _sendReport(report: ErrorReport): Promise<void> {
    if (import.meta.env.DEV && report.severity === "fatal") {
      console.group(`[ErrorTracker] FATAL`);
      console.error(report.message);
      console.groupEnd();
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    try {
      const token = storageService.getItem<string>("access_token") ?? "";
      const base =
        (import.meta as { env: Record<string, string> }).env.VITE_API_URL ??
        "/api/v1";
      await fetch(`${base}/system/error-report`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(report),
        keepalive: true,
        signal: controller.signal,
      });
      clearTimeout(timer);
      // Remove from pending on success — beacon would duplicate it otherwise
      const idx = this.pendingReports.indexOf(report);
      if (idx !== -1) this.pendingReports.splice(idx, 1);
    } catch {
      clearTimeout(timer);
      if (import.meta.env.DEV) {
        console.warn("[ErrorTracker] Sink unreachable:", report.message);
      }
      // Leave in pending so beacon can retry on pagehide
    }
  }
}

export const errorTracker = new ErrorTracker();
