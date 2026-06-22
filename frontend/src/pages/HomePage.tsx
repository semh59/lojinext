import { lazy, Suspense } from "react";

import { useAuth } from "../context/AuthContext";

const TodayPage = lazy(() => import("./TodayPage"));
const DashboardPage = lazy(() => import("./DashboardPage"));

const TRIAGE_ROLES = new Set(["admin", "super_admin", "fleet_manager"]);

/**
 * RV2.9 — Hibrit `/` route. Plan §1 Karar 5.
 * canSeeTriage rolüne sahip kullanıcılar TodayPage'i, diğerleri DashboardPage'i
 * görür. Eski dashboard `/legacy-dashboard` altında 3 ay korunur.
 */
export default function HomePage() {
  const { user } = useAuth();
  const canSeeTriage = user?.role ? TRIAGE_ROLES.has(user.role) : false;
  return (
    <Suspense fallback={null}>
      {canSeeTriage ? <TodayPage /> : <DashboardPage />}
    </Suspense>
  );
}
