import React from "react";
import ReactDOM from "react-dom/client";
import {
  QueryClient,
  QueryCache,
  MutationCache,
  QueryClientProvider,
} from "@tanstack/react-query";
import { onCLS, onINP, onLCP, onTTFB } from "web-vitals";
import App from "./App.tsx";
import "./index.css";
import "./i18n.ts";
import { errorTracker } from "./services/error-tracker";

// Install global listeners (window.onerror, unhandledrejection, pagehide/sendBeacon)
errorTracker.install();

// ── Web Vitals ─────────────────────────────────────────────────────────────
onLCP(({ value }) => {
  if (value > 4000)
    errorTracker.captureMessage(`Slow LCP: ${Math.round(value)}ms`, "warning", {
      metric: "LCP",
      value_ms: value,
      path: window.location.pathname,
    });
});

onINP(({ value }) => {
  const severity = value > 500 ? "error" : "warning";
  if (value > 200)
    errorTracker.captureMessage(`Poor INP: ${Math.round(value)}ms`, severity, {
      metric: "INP",
      value_ms: value,
      path: window.location.pathname,
    });
});

onCLS(({ value }) => {
  if (value > 0.25)
    errorTracker.captureMessage(`Poor CLS: ${value.toFixed(3)}`, "warning", {
      metric: "CLS",
      value,
      path: window.location.pathname,
    });
});

onTTFB(({ value }) => {
  if (value > 2000)
    errorTracker.captureMessage(
      `Slow TTFB: ${Math.round(value)}ms`,
      "warning",
      { metric: "TTFB", value_ms: value, path: window.location.pathname },
    );
});

// ── console.error monkey-patch ─────────────────────────────────────────────
const _originalConsoleError = console.error.bind(console);
console.error = (...args: unknown[]) => {
  _originalConsoleError(...args);
  const message = args.map(String).join(" ").slice(0, 500);
  const isNoise = [
    /React DevTools/i,
    /Warning: Each child/i,
    /Warning: ReactDOM/i,
    /\[HMR\]/,
    /hot reload/i,
    /Download the React DevTools/i,
  ].some((p) => p.test(message));
  if (!isNoise) {
    errorTracker.captureMessage(message, "warning", {
      source: "console.error",
    });
  }
};

// ── Resource loading failure ───────────────────────────────────────────────
if ("PerformanceObserver" in window) {
  try {
    const resourceObserver = new PerformanceObserver((list) => {
      list.getEntries().forEach((entry) => {
        const r = entry as PerformanceResourceTiming;
        // transferSize=0 + decodedBodySize=0 + duration>0 → load failed
        if (r.transferSize === 0 && r.decodedBodySize === 0 && r.duration > 0) {
          if (r.duration < 5) return; // cancelled requests
          errorTracker.captureMessage(
            `Resource load failed: ${r.name.split("?")[0]}`,
            "warning",
            { resource_type: r.initiatorType, url: r.name.slice(0, 200) },
          );
        }
      });
    });
    resourceObserver.observe({ type: "resource", buffered: true });
  } catch {
    // Browser doesn't support this observer type
  }
}

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
  queryCache: new QueryCache({
    onError: (error, query) => {
      const status = (error as { response?: { status?: number } }).response
        ?.status;
      if (!status || status >= 500) {
        errorTracker.captureApiError({
          severity: "error",
          path: String(query.queryKey[0] ?? "query"),
          traceId: errorTracker.getLastTraceId(),
          extra: { queryKey: query.queryKey, status },
        });
      }
    },
  }),
  mutationCache: new MutationCache({
    onError: (error, _vars, _ctx, mutation) => {
      const status = (error as { response?: { status?: number } }).response
        ?.status;
      if (!status || status >= 500) {
        errorTracker.captureApiError({
          severity: "error",
          path: String(mutation.options.mutationKey?.[0] ?? "mutation"),
          traceId: errorTracker.getLastTraceId(),
          extra: { status },
        });
      }
    },
  }),
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
