/**
 * Wraps a Zustand state creator so that any exception thrown by `set`
 * is captured and re-thrown. Apply inside `persist(...)`, not outside,
 * so that Zustand's `.persist` type augmentation is preserved.
 *
 * Usage:
 *   create<T>()(persist(withErrorTracking((set) => ({ ... })), opts))
 */
import type { StateCreator } from "zustand";
import { errorTracker } from "./error-tracker";

function safeStringify(val: unknown): string | undefined {
  try {
    return JSON.stringify(val)?.slice(0, 100);
  } catch {
    return "[circular]";
  }
}

export function withErrorTracking<T>(
  creator: StateCreator<T>,
): StateCreator<T> {
  return (set, get, api) => {
    const guardedSet = (...args: any[]) => {
      try {
        (set as (...a: any[]) => void)(...args);
      } catch (err) {
        errorTracker.capture(
          err instanceof Error ? err : new Error(String(err)),
          {
            severity: "error",
            extra: {
              store: "zustand",
              action:
                typeof args[0] === "function" ? "fn" : safeStringify(args[0]),
            },
          },
        );
        throw err;
      }
    };
    return creator(guardedSet, get, api);
  };
}
