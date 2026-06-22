import { useEffect, useRef } from "react";
import { errorTracker } from "../services/error-tracker";

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
  threshold: number = 5,
): void {
  const renderCount = useRef(0);
  const windowStart = useRef(Date.now());

  useEffect(() => {
    renderCount.current += 1;
    const elapsed = Date.now() - windowStart.current;

    if (elapsed < 100 && renderCount.current > threshold) {
      errorTracker.captureMessage(
        `Excessive re-renders: ${componentName} (${renderCount.current}× in ${elapsed}ms)`,
        "warning",
        {
          component: componentName,
          render_count: renderCount.current,
          elapsed_ms: elapsed,
          path: window.location.pathname,
        },
      );
      // Reset window after reporting to avoid repeated spam.
      // Use 1 (not 0) so this render counts toward the next detection window.
      renderCount.current = 1;
      windowStart.current = Date.now();
    } else if (elapsed >= 100) {
      renderCount.current = 1;
      windowStart.current = Date.now();
    }
  });
}
