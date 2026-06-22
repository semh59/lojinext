import { useSearchParams } from "react-router-dom";
import { useCallback, useMemo } from "react";

/**
 * A hook to manage state in the URL search parameters.
 * Supports strings, numbers, and booleans with automatic type conversion.
 */
export function useUrlState<
  T extends Record<string, string | number | boolean | undefined>,
>(initialState: T) {
  const [searchParams, setSearchParams] = useSearchParams();

  // Parse current URL params based on initialState types
  const urlState = useMemo(() => {
    const state = { ...initialState } as T;

    Object.keys(initialState).forEach((key) => {
      const value = searchParams.get(key);
      if (value === null) return;

      const initialValue = initialState[key];

      if (typeof initialValue === "number") {
        const num = Number(value);
        if (!isNaN(num)) {
          (state as any)[key] = num;
        }
      } else if (typeof initialValue === "boolean") {
        (state as any)[key] = value === "true";
      } else {
        (state as any)[key] = value;
      }
    });

    return state;
  }, [searchParams, initialState]);

  /**
   * Update URL parameters. Supports partial updates.
   * @param newState Partial state to update
   * @param options Navigation options (replace vs push)
   */
  const setUrlState = useCallback(
    (
      newState: Partial<T> | ((prev: T) => Partial<T>),
      options: { replace?: boolean } = { replace: true },
    ) => {
      setSearchParams(
        (prevParams) => {
          const nextParams = new URLSearchParams(prevParams);
          const updates =
            typeof newState === "function" ? newState(urlState) : newState;

          Object.entries(updates).forEach(([key, value]) => {
            if (
              value === undefined ||
              value === "" ||
              value === initialState[key]
            ) {
              nextParams.delete(key);
            } else {
              nextParams.set(key, String(value));
            }
          });
          return nextParams;
        },
        { replace: options.replace },
      );
    },
    [setSearchParams, urlState, initialState],
  );

  return [urlState, setUrlState] as const;
}
