import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { recordPageView } from "../api/analytics";

/**
 * Faz 3 — route değişiminde sayfa görüntüleme kaydı (fire-and-forget).
 * Aynı path için arka arkaya tekrar göndermez (dedup).
 */
export function usePageViewTracking(): void {
  const location = useLocation();
  const lastPath = useRef<string | null>(null);

  useEffect(() => {
    if (lastPath.current === location.pathname) return;
    lastPath.current = location.pathname;
    void recordPageView(location.pathname);
  }, [location.pathname]);
}
