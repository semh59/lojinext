# Error Detector — Plan 3: Frontend Probes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the frontend error tracking to catch every silent failure: axios 4xx/5xx, console.error, Web Vitals (INP included), resource load failures, Zustand mutations, React Query errors, excessive re-renders, and unload-time errors via sendBeacon.

**Architecture:** `error-tracker.ts` is the single sink. All probes call `errorTracker.captureApiError()` or `errorTracker.capture()`. Backend `trace_id` correlation is threaded through every error report. `sendBeacon` flushes pending events on page unload.

**Tech Stack:** TypeScript, axios, web-vitals (npm), Zustand middleware, React Query cache hooks, PerformanceObserver, navigator.sendBeacon.

**Depends on:** Plan 1 (backend `/system/error-report-batch` endpoint is in Plan 4 — use single `/system/error-report` until Plan 4 lands, then switch).

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `frontend/src/services/error-tracker.ts` | Add captureApiError, session_id, sendBeacon flush, getLastTraceId |
| Modify | `frontend/src/services/api/axios-instance.ts` | Response interceptor for 4xx/5xx + trace_id capture |
| Modify | `frontend/src/main.tsx` | Install error tracker, console.error patch, Web Vitals, resource observer |
| Create | `frontend/src/hooks/use-render-guard.ts` | Excessive re-render detector |
| Modify | `frontend/src/stores/use-trip-store.ts` | Add Zustand error middleware |
| Modify | `frontend/src/stores/use-ai-store.ts` | Add Zustand error middleware |
| Modify | `frontend/src/main.tsx` | QueryClient with global error handlers |
| Create | `frontend/src/services/error-middleware.ts` | Zustand error middleware (shared) |
| Create | `frontend/src/components/common/__tests__/ErrorBoundary.test.tsx` | Tests |

---

## Task 1: Upgrade error-tracker.ts

**Files:**
- Modify: `frontend/src/services/error-tracker.ts`

- [ ] **Step 1: Install web-vitals package**

```bash
cd frontend
npm install web-vitals
```

- [ ] **Step 2: Replace error-tracker.ts with upgraded version**

```typescript
// frontend/src/services/error-tracker.ts
/**
 * Unified frontend error tracker.
 * - captureApiError: axios 4xx/5xx with trace_id correlation
 * - capture: JS errors, component stack, React boundary
 * - captureMessage: console.error, Web Vitals, resource failures
 * - sendBeacon flush: ensures errors on pagehide are delivered
 */

import axiosInstance from './api/axios-instance';

export interface ErrorReport {
  message: string;
  stack?: string;
  componentStack?: string;
  url: string;
  userAgent: string;
  timestamp: string;
  severity: 'error' | 'warning' | 'fatal';
  backend_trace_id?: string;
  frontend_session_id: string;
  extra?: Record<string, unknown>;
}

export interface ApiErrorReport {
  status?: number;
  path: string;
  traceId?: string;
  severity: ErrorReport['severity'];
  errorCode?: string;
  extra?: Record<string, unknown>;
}

// Noise patterns: never report these (React DevTools, HMR, etc.)
const CONSOLE_NOISE_PATTERNS = [
  /React DevTools/i,
  /\[HMR\]/,
  /Warning: ReactDOM.render/i,
  /Warning: Each child in a list/i,
  /Download the React DevTools/i,
];

class ErrorTracker {
  private readonly sessionId: string;
  private lastTraceId: string = '';
  private reportedErrors = new Map<string, number>();
  private pendingReports: ErrorReport[] = [];
  private readonly MAX_REPORTS_PER_KEY = 3;
  private readonly COOLDOWN_MS = 60_000;
  private readonly MAX_PENDING = 50;

  constructor() {
    this.sessionId = this._generateSessionId();
  }

  private _generateSessionId(): string {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  }

  // ── Public API ──────────────────────────────────────────────────────────

  /** Called by axios interceptor for all non-2xx responses. */
  captureApiError(report: ApiErrorReport): void {
    const severity = report.severity;
    const message = [
      `API ${report.status ?? 'NETWORK'} ${report.path}`,
      report.errorCode ? `[${report.errorCode}]` : '',
    ].filter(Boolean).join(' ');

    this.capture(
      Object.assign(new Error(message), { stack: undefined }),
      {
        severity,
        extra: {
          status: report.status,
          path: report.path,
          error_code: report.errorCode,
          ...report.extra,
        },
        traceId: report.traceId,
      }
    );
  }

  /** Capture an Error object (from ErrorBoundary, window.onerror, etc.). */
  capture(
    error: Error,
    extra?: {
      componentStack?: string;
      severity?: ErrorReport['severity'];
      extra?: Record<string, unknown>;
      traceId?: string;
    }
  ): void {
    const key = `${error.message}:${error.stack?.slice(0, 200) ?? ''}`;
    const now = Date.now();
    const lastReport = this.reportedErrors.get(key) ?? 0;

    if (now - lastReport < this.COOLDOWN_MS) return;
    this.reportedErrors.set(key, now);

    const countKey = `count:${key}`;
    const count = this.reportedErrors.get(countKey) ?? 0;
    if (count >= this.MAX_REPORTS_PER_KEY) return;
    this.reportedErrors.set(countKey, count + 1);

    const report: ErrorReport = {
      message: error.message,
      stack: error.stack,
      componentStack: extra?.componentStack,
      url: window.location.href,
      userAgent: navigator.userAgent,
      timestamp: new Date().toISOString(),
      severity: extra?.severity ?? 'error',
      backend_trace_id: extra?.traceId ?? this.lastTraceId ?? undefined,
      frontend_session_id: this.sessionId,
      extra: extra?.extra,
    };

    this._enqueue(report);
  }

  /** Capture a plain message (Web Vitals, console.error, resource failures). */
  captureMessage(
    message: string,
    severity: ErrorReport['severity'] = 'warning',
    extra?: Record<string, unknown>
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
    window.addEventListener('error', (event) => {
      if (event.error) this.capture(event.error, { severity: 'error' });
    });

    window.addEventListener('unhandledrejection', (event) => {
      const error =
        event.reason instanceof Error
          ? event.reason
          : new Error(String(event.reason));
      this.capture(error, { severity: 'warning' });
    });

    // Flush pending reports on page unload (sendBeacon guarantees delivery)
    window.addEventListener('pagehide', () => {
      this._flushBeacon();
    });
  }

  /** Flush pending reports via sendBeacon (called on pagehide). */
  flushPending(): ErrorReport[] {
    return this.pendingReports.splice(0);
  }

  reset(): void {
    this.reportedErrors.clear();
    this.pendingReports = [];
  }

  // ── Internal ────────────────────────────────────────────────────────────

  private _enqueue(report: ErrorReport): void {
    if (this.pendingReports.length < this.MAX_PENDING) {
      this.pendingReports.push(report);
    }
    this._sendReport(report);
  }

  private _flushBeacon(): void {
    const pending = this.flushPending();
    if (pending.length === 0) return;
    // sendBeacon works even during page unload; no await needed
    navigator.sendBeacon(
      '/api/v1/system/error-report-batch',
      JSON.stringify(pending)
    );
  }

  private async _sendReport(report: ErrorReport): Promise<void> {
    if (import.meta.env.DEV && report.severity === 'fatal') {
      console.group(`[ErrorTracker] FATAL`);
      console.error(report.message);
      console.groupEnd();
    }
    try {
      await axiosInstance.post('/system/error-report', report);
    } catch {
      if (import.meta.env.DEV) {
        console.warn('[ErrorTracker] Sink unreachable:', report.message);
      }
    }
  }
}

export const errorTracker = new ErrorTracker();
```

- [ ] **Step 3: Run frontend type check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: No errors related to error-tracker.ts.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/error-tracker.ts
git commit -m "feat(frontend): upgrade error-tracker with captureApiError, trace_id correlation, sendBeacon flush"
```

---

## Task 2: Axios Interceptor

**Files:**
- Modify: `frontend/src/services/api/axios-instance.ts`

- [ ] **Step 1: Read current axios-instance.ts**

```bash
cat frontend/src/services/api/axios-instance.ts
```

- [ ] **Step 2: Add response interceptor**

Find the existing interceptors section and add/extend the response interceptor:

```typescript
// In the response interceptor (after existing 401 refresh logic):

// Add at the top of the response success handler:
axiosInstance.interceptors.response.use(
  (response) => {
    // Capture backend trace_id for correlation
    const traceId = response.headers['x-correlation-id'];
    if (traceId) {
      errorTracker.setLastTraceId(traceId as string);
    }
    return response;
  },
  async (error: AxiosError) => {
    // ... existing 401 refresh logic stays here ...

    // After refresh logic: report non-401 errors
    const status = error.response?.status;
    const traceId = error.response?.headers?.['x-correlation-id'] as string | undefined;
    const path = error.config?.url ?? 'unknown';
    const errorCode = (error.response?.data as Record<string, unknown> | undefined)
      ?.error
      ? ((error.response?.data as { error: { code?: string } }).error.code)
      : undefined;

    // Determine severity
    const severity: 'fatal' | 'error' | 'warning' =
      !status              ? 'fatal'    // network error
      : status >= 500      ? 'error'
      : status === 401     ? 'warning'  // auth — already redirected
      : status === 403     ? 'warning'
      : 'warning';

    errorTracker.captureApiError({ status, path, traceId, severity, errorCode });

    return Promise.reject(error);
  }
);
```

> **Note:** Preserve all existing 401 token-refresh logic. The new code adds `errorTracker` calls alongside it.

Import `errorTracker` at the top:
```typescript
import { errorTracker } from '../error-tracker';
```

- [ ] **Step 3: Run type check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/api/axios-instance.ts
git commit -m "feat(frontend): axios interceptor captures all 4xx/5xx with trace_id correlation"
```

---

## Task 3: Web Vitals + console.error Patch

**Files:**
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Add Web Vitals + console.error patch to main.tsx**

In `frontend/src/main.tsx`, after `errorTracker.install()`:

```typescript
import { errorTracker } from './services/error-tracker';
import { onCLS, onINP, onLCP, onTTFB, onFCP } from 'web-vitals';

// Install global listeners (window.onerror, unhandledrejection, pagehide/sendBeacon)
errorTracker.install();

// ── Web Vitals ────────────────────────────────────────────────────────────
// Thresholds: https://web.dev/vitals/
onLCP(({ value }) => {
  if (value > 4000)
    errorTracker.captureMessage(`Slow LCP: ${Math.round(value)}ms`, 'warning',
      { metric: 'LCP', value_ms: value, path: window.location.pathname });
});

onINP(({ value }) => {
  const severity = value > 500 ? 'error' : 'warning';
  if (value > 200)
    errorTracker.captureMessage(`Poor INP: ${Math.round(value)}ms`, severity,
      { metric: 'INP', value_ms: value, path: window.location.pathname });
});

onCLS(({ value }) => {
  if (value > 0.25)
    errorTracker.captureMessage(`Poor CLS: ${value.toFixed(3)}`, 'warning',
      { metric: 'CLS', value, path: window.location.pathname });
});

onTTFB(({ value }) => {
  if (value > 2000)
    errorTracker.captureMessage(`Slow TTFB: ${Math.round(value)}ms`, 'warning',
      { metric: 'TTFB', value_ms: value, path: window.location.pathname });
});

// ── console.error monkey-patch ────────────────────────────────────────────
// Catches errors logged by libraries (React warnings, third-party errors).
const _originalConsoleError = console.error.bind(console);
console.error = (...args: unknown[]) => {
  _originalConsoleError(...args);
  const message = args.map(String).join(' ').slice(0, 500);
  // Filter out known noise
  const isNoise = [
    /React DevTools/i,
    /Warning: Each child/i,
    /Warning: ReactDOM/i,
    /\[HMR\]/,
    /hot reload/i,
    /Download the React DevTools/i,
  ].some((p) => p.test(message));
  if (!isNoise) {
    errorTracker.captureMessage(message, 'warning', { source: 'console.error' });
  }
};

// ── Resource loading failure ──────────────────────────────────────────────
// Detects 404/failed script, CSS, image, font loads.
if ('PerformanceObserver' in window) {
  try {
    const resourceObserver = new PerformanceObserver((list) => {
      list.getEntries().forEach((entry) => {
        const r = entry as PerformanceResourceTiming;
        // transferSize=0 + decodedBodySize=0 + duration>0 → load failed
        if (r.transferSize === 0 && r.decodedBodySize === 0 && r.duration > 0) {
          // Exclude cancelled requests (duration < 5ms)
          if (r.duration < 5) return;
          errorTracker.captureMessage(
            `Resource load failed: ${r.name.split('?')[0]}`,
            'warning',
            { resource_type: r.initiatorType, url: r.name.slice(0, 200) }
          );
        }
      });
    });
    resourceObserver.observe({ type: 'resource', buffered: true });
  } catch {
    // Browser doesn't support this observer type
  }
}
```

- [ ] **Step 2: Run type check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/main.tsx
git commit -m "feat(frontend): add Web Vitals (LCP/INP/CLS/TTFB), console.error patch, resource load failure detection"
```

---

## Task 4: Zustand Error Middleware

**Files:**
- Create: `frontend/src/services/error-middleware.ts`
- Modify: `frontend/src/stores/use-trip-store.ts`
- Modify: `frontend/src/stores/use-ai-store.ts`

- [ ] **Step 1: Create shared Zustand error middleware**

```typescript
// frontend/src/services/error-middleware.ts
/**
 * Zustand middleware that captures state mutation exceptions.
 * Wraps the `set` function — if a setter throws, the error is reported
 * and re-thrown so the store is not left in an inconsistent state.
 */
import type { StateCreator, StoreMutatorIdentifier } from 'zustand';
import { errorTracker } from './error-tracker';

type ErrorMiddleware = <
  T,
  Mps extends [StoreMutatorIdentifier, unknown][] = [],
  Mcs extends [StoreMutatorIdentifier, unknown][] = [],
>(
  f: StateCreator<T, Mps, Mcs>
) => StateCreator<T, Mps, Mcs>;

export const errorMiddleware: ErrorMiddleware = (config) => (set, get, api) =>
  config(
    (...args) => {
      try {
        set(...args);
      } catch (err) {
        errorTracker.capture(
          err instanceof Error ? err : new Error(String(err)),
          {
            severity: 'error',
            extra: {
              store: 'zustand',
              action: typeof args[0] === 'function' ? 'fn' : JSON.stringify(args[0])?.slice(0, 100),
            },
          }
        );
        throw err; // Re-throw to avoid silent inconsistent state
      }
    },
    get,
    api
  );
```

- [ ] **Step 2: Add errorMiddleware to use-trip-store.ts**

In `frontend/src/stores/use-trip-store.ts`, wrap the store creator:

```typescript
import { errorMiddleware } from '../services/error-middleware';

// Change:
//   create<TripStore>()(persist(devtools(...), ...))
// To:
//   create<TripStore>()(errorMiddleware(persist(devtools(...), ...)))
```

- [ ] **Step 3: Add errorMiddleware to use-ai-store.ts**

Same pattern as use-trip-store.ts.

- [ ] **Step 4: Run type check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/error-middleware.ts frontend/src/stores/use-trip-store.ts frontend/src/stores/use-ai-store.ts
git commit -m "feat(frontend): add Zustand error middleware to trip + AI stores"
```

---

## Task 5: React Query Global Error Handler

**Files:**
- Modify: `frontend/src/main.tsx` (or wherever QueryClient is instantiated)

- [ ] **Step 1: Find QueryClient instantiation**

```bash
grep -rn "new QueryClient" frontend/src/ --include="*.tsx" --include="*.ts"
```

- [ ] **Step 2: Add global error handlers**

Replace the bare `new QueryClient({})` (or add to existing config):

```typescript
import { QueryClient, QueryCache, MutationCache } from '@tanstack/react-query';
import { errorTracker } from './services/error-tracker';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5 * 60 * 1000,
    },
  },
  queryCache: new QueryCache({
    onError: (error, query) => {
      // Only report if not a standard 4xx (axios interceptor already handles those)
      const status = (error as { response?: { status?: number } }).response?.status;
      if (!status || status >= 500) {
        errorTracker.captureApiError({
          severity: 'error',
          path: String(query.queryKey[0] ?? 'query'),
          traceId: errorTracker.getLastTraceId(),
          extra: { queryKey: query.queryKey, status },
        });
      }
    },
  }),
  mutationCache: new MutationCache({
    onError: (error, _vars, _ctx, mutation) => {
      const status = (error as { response?: { status?: number } }).response?.status;
      if (!status || status >= 500) {
        errorTracker.captureApiError({
          severity: 'error',
          path: String(mutation.options.mutationKey?.[0] ?? 'mutation'),
          traceId: errorTracker.getLastTraceId(),
          extra: { status },
        });
      }
    },
  }),
});
```

- [ ] **Step 3: Run type check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/main.tsx
git commit -m "feat(frontend): add React Query global error handlers for queryCache + mutationCache"
```

---

## Task 6: useRenderGuard Hook

**Files:**
- Create: `frontend/src/hooks/use-render-guard.ts`
- Create: `frontend/src/hooks/__tests__/use-render-guard.test.ts`

- [ ] **Step 1: Write failing test**

```typescript
// frontend/src/hooks/__tests__/use-render-guard.test.ts
import { renderHook } from '@testing-library/react';
import { vi, describe, it, expect } from 'vitest';

// Mock errorTracker before importing the hook
vi.mock('../../services/error-tracker', () => ({
  errorTracker: { captureMessage: vi.fn() },
}));

import { useRenderGuard } from '../use-render-guard';
import { errorTracker } from '../../services/error-tracker';

describe('useRenderGuard', () => {
  it('does not emit on normal render count', () => {
    const { rerender } = renderHook(() => useRenderGuard('TestComponent', 5));
    rerender();
    rerender();
    expect(errorTracker.captureMessage).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd frontend && npx vitest run src/hooks/__tests__/use-render-guard.test.ts
```

- [ ] **Step 3: Implement useRenderGuard**

```typescript
// frontend/src/hooks/use-render-guard.ts
import { useEffect, useRef } from 'react';
import { errorTracker } from '../services/error-tracker';

/**
 * Detects excessive re-renders (potential render loop or missing memoization).
 * Reports to errorTracker if the component re-renders more than `threshold`
 * times within a 100ms window.
 *
 * Usage: Add to any component suspected of excessive re-renders:
 *   useRenderGuard('TripTable')
 */
export function useRenderGuard(
  componentName: string,
  threshold: number = 5
): void {
  const renderCount = useRef(0);
  const windowStart = useRef(Date.now());

  useEffect(() => {
    renderCount.current += 1;
    const elapsed = Date.now() - windowStart.current;

    if (elapsed < 100 && renderCount.current > threshold) {
      errorTracker.captureMessage(
        `Excessive re-renders: ${componentName} (${renderCount.current}× in ${elapsed}ms)`,
        'warning',
        { component: componentName, render_count: renderCount.current, elapsed_ms: elapsed }
      );
      // Reset window after reporting to avoid repeated spam
      renderCount.current = 0;
      windowStart.current = Date.now();
    } else if (elapsed >= 100) {
      // New time window
      renderCount.current = 1;
      windowStart.current = Date.now();
    }
  });
}
```

- [ ] **Step 4: Run test**

```bash
cd frontend && npx vitest run src/hooks/__tests__/use-render-guard.test.ts
```
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/use-render-guard.ts frontend/src/hooks/__tests__/use-render-guard.test.ts
git commit -m "feat(frontend): add useRenderGuard hook for excessive re-render detection"
```

---

## Task 7: Backend Batch Endpoint Stub (for sendBeacon)

`sendBeacon` sends to `/api/v1/system/error-report-batch`. This endpoint is fully implemented in Plan 4, but to avoid 404 errors when users close the page before Plan 4 is deployed, add a minimal stub now.

**Files:**
- Modify: `app/api/v1/endpoints/system.py`

- [ ] **Step 1: Add batch endpoint stub**

```python
# In app/api/v1/endpoints/system.py, add after the existing /error-report endpoint:

from typing import List

@router.post("/error-report-batch", status_code=204)
@limiter.limit("5/minute")
async def receive_frontend_error_batch(
    reports: List[FrontendErrorReport],
    request: Request,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Accept batch of client-side JS error reports (sent via navigator.sendBeacon)."""
    client_ip = request.client.host if request.client else "unknown"
    for report in reports[:20]:  # cap at 20 per batch
        logger.warning(
            "frontend_error_batch severity=%s url=%s ip=%s user_id=%s msg=%s",
            report.severity, report.url, client_ip, current_user.id,
            report.message[:200],
        )
        if report.severity in ("error", "fatal"):
            asyncio.create_task(notify_error(
                level="critical" if report.severity == "fatal" else "error",
                message=f"[Frontend batch uid={current_user.id}] {report.message[:300]}",
                path=report.url,
            ))
```

- [ ] **Step 2: Run tests**

```bash
pytest app/tests/ -k "system" -q
```

- [ ] **Step 3: Commit**

```bash
git add app/api/v1/endpoints/system.py
git commit -m "feat(frontend): add /error-report-batch endpoint for sendBeacon delivery"
```

---

## Self-Review Checklist

- [x] error-tracker.ts: captureApiError, setLastTraceId/getLastTraceId, sendBeacon flush, frontend_session_id, pending queue ✓
- [x] axios-instance.ts: response interceptor captures all non-2xx, stores trace_id, determines severity ✓
- [x] Web Vitals: LCP (>4s), INP (>200ms warn, >500ms error), CLS (>0.25), TTFB (>2s) ✓
- [x] console.error monkey-patch with noise filtering ✓
- [x] Resource load failure via PerformanceObserver ✓
- [x] Zustand error middleware in both stores ✓
- [x] React Query global queryCache + mutationCache onError ✓
- [x] useRenderGuard hook (5+ renders / 100ms) ✓
- [x] /error-report-batch stub endpoint ✓
- [x] No TBD/TODO placeholders ✓
- [x] Type names consistent (ErrorReport, ApiErrorReport) ✓
