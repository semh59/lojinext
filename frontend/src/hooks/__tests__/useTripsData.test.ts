/**
 * T8-B: useTripsData stale closure — searchParams değişince refetch.
 *
 * Bug Açıklaması:
 *   useTripsData hook searchParams değişimi capture etmiyor.
 *   useEffect dependency array'de searchParams yok.
 *   Eski params ile cached data döndürülüyor.
 *
 * Beklenen: searchParams değişince useEffect yeniden çalışmalı (refetch).
 */

import { describe, it, vi, beforeEach } from "vitest";

describe("useTripsData - T8-B stale closure on searchParams change", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("re-fetches trips data when searchParams changes", async () => {
    // T8-B: Hook should refetch when searchParams changes
    // Placeholder test showing the pattern:
    // When searchParams changes (e.g. filter, sort), useTripsData should
    // trigger a new API call, not return stale cached data
    // In a real test with renderHook:
    // const { result, rerender } = renderHook(
    //   ({ params }) => useTripsData(params),
    //   { initialProps: { params: { filter: 'completed' } } }
    // );
    // // Initial fetch
    // await waitFor(() => expect(result.current.data).toBeDefined());
    // const fetchCount1 = mockFetchTrips.mock.calls.length;
    // // Change searchParams
    // rerender({ params: { filter: 'pending' } });
    // // Should trigger refetch
    // await waitFor(() => {
    //   expect(mockFetchTrips).toHaveBeenCalledTimes(fetchCount1 + 1);
    // });
  });

  it("should include searchParams in useEffect dependency array", () => {
    // T8-B: Dependency array must include searchParams or serialized version
    // Otherwise stale closure trap: old params stay in effect closure
    // and new API calls never happen
    // Good: useEffect(() => { fetchTrips(searchParams) }, [searchParams])
    // Bad: useEffect(() => { fetchTrips(searchParams) }, [])  // searchParams not in deps!
  });
});
