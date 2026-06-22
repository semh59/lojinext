import { Suspense, lazy } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { PrivateRoute } from "./components/auth/PrivateRoute";
import ErrorBoundary from "./components/common/ErrorBoundary";
import { AppToaster } from "./components/ui/AppToaster";
import { AuthProvider } from "./context/AuthContext";
import { NotificationProvider } from "./context/NotificationContext";
import LoginPage from "./pages/LoginPage";

const HomePage = lazy(() => import("./pages/HomePage"));
const MonitoringPage = lazy(() => import("./pages/MonitoringPage"));
const AlertsPage = lazy(() => import("./pages/AlertsPage"));
const PredictionsPage = lazy(() => import("./pages/PredictionsPage"));
const TripsPage = lazy(() => import("./pages/TripsPage"));
const FleetPage = lazy(() => import("./pages/FleetPage"));
const DriversPage = lazy(() => import("./pages/DriversPage"));
const FuelPage = lazy(() => import("./pages/FuelPage"));
const ReportsStudioPage = lazy(() => import("./pages/ReportsStudioPage"));
const RouteLabPage = lazy(() => import("./pages/RouteLabPage"));
const ExecutivePage = lazy(() => import("./pages/ExecutivePage"));
const TodayPage = lazy(() => import("./pages/TodayPage"));
const FleetInsightsPage = lazy(() => import("./pages/FleetInsightsPage"));
const LocationsPage = lazy(() => import("./pages/LocationsPage"));
const CoachingPage = lazy(() => import("./pages/CoachingPage"));

const ProfilePage = lazy(() => import("./pages/ProfilePage"));

const AdminOverviewPage = lazy(() => import("./pages/admin/OverviewPage"));
const AdminConfigurationPage = lazy(
  () => import("./pages/admin/KonfigurasyonPage"),
);
const AdminUsersPage = lazy(() => import("./pages/admin/KullanicilarPage"));
const AdminRolesPage = lazy(() => import("./pages/admin/RollerPage"));
const AdminAccuracyPage = lazy(() => import("./pages/admin/DogrulukPage"));
const AdminAttributionPage = lazy(() => import("./pages/admin/AtamaPage"));
const AdminMlManagementPage = lazy(() => import("./pages/admin/MLYonetimPage"));
const AdminAnalyticsPage = lazy(() => import("./pages/admin/AnalyticsPage"));
const AdminMaintenancePage = lazy(() => import("./pages/admin/BakimPage"));
const AdminDataManagementPage = lazy(
  () => import("./pages/admin/VeriYonetimPage"),
);
const SystemHealthPage = lazy(() => import("./pages/admin/SistemSaglikPage"));
const AdminNotificationsPage = lazy(
  () => import("./pages/admin/BildirimlerPage"),
);
const AppLayout = lazy(() => import("./layouts/AppLayout"));
const AdminLayout = lazy(() => import("./pages/admin/AdminLayout"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

function PageLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-base">
      <div className="flex flex-col items-center gap-6">
        <div className="h-12 w-12 animate-spin rounded-full border-[3.5px] border-accent/10 border-t-accent" />
        <span className="animate-pulse text-[10px] font-bold uppercase tracking-[0.3em] text-secondary">
          LojiNext
        </span>
      </div>
    </div>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <NotificationProvider>
            <AppToaster />
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route path="/login" element={<LoginPage />} />

                <Route element={<PrivateRoute />}>
                  {/* ── Operatör sayfaları — AppLayout ── */}
                  <Route element={<AppLayout />}>
                    <Route path="/trips" element={<TripsPage />} />
                    <Route path="/fuel" element={<FuelPage />} />
                    <Route path="/fleet" element={<FleetPage />} />
                    <Route
                      path="/vehicles"
                      element={<Navigate to="/fleet?tab=vehicles" replace />}
                    />
                    <Route path="/drivers" element={<DriversPage />} />
                    <Route path="/locations" element={<LocationsPage />} />
                    <Route path="/coaching" element={<CoachingPage />} />
                    <Route path="/reports" element={<ReportsStudioPage />} />
                    <Route path="/route-lab" element={<RouteLabPage />} />
                    <Route
                      path="/reports/legacy"
                      element={<Navigate to="/reports" replace />}
                    />
                    <Route path="/executive" element={<ExecutivePage />} />
                    <Route path="/today" element={<TodayPage />} />
                    <Route
                      path="/insights/fleet"
                      element={<FleetInsightsPage />}
                    />
                    <Route path="/profile" element={<ProfilePage />} />
                    <Route
                      path="/settings"
                      element={<Navigate to="/admin" replace />}
                    />
                    <Route path="/" element={<HomePage />} />
                    <Route
                      path="/legacy-dashboard"
                      element={<Navigate to="/" replace />}
                    />
                    <Route
                      path="/maintenance"
                      element={<AdminMaintenancePage />}
                    />
                    <Route path="/monitoring" element={<MonitoringPage />} />
                    <Route path="/alerts" element={<AlertsPage />} />
                    <Route path="/predictions" element={<PredictionsPage />} />
                    <Route
                      path="/users"
                      element={<Navigate to="/trips" replace />}
                    />
                  </Route>

                  {/* ── Admin sayfaları — AdminLayout (kendi sidebar) ── */}
                  <Route
                    element={<PrivateRoute requiredPermission="admin:read" />}
                  >
                    <Route element={<AdminLayout />}>
                      <Route path="/admin">
                        <Route index element={<AdminOverviewPage />} />
                        <Route
                          path="konfig"
                          element={<AdminConfigurationPage />}
                        />
                        <Route
                          path="kullanicilar"
                          element={<AdminUsersPage />}
                        />
                        <Route path="roller" element={<AdminRolesPage />} />
                        <Route
                          path="dogruluk"
                          element={<AdminAccuracyPage />}
                        />
                        <Route
                          path="atama"
                          element={<AdminAttributionPage />}
                        />
                        <Route path="ml" element={<AdminMlManagementPage />} />
                        <Route
                          path="analitik"
                          element={<AdminAnalyticsPage />}
                        />
                        <Route
                          path="veri"
                          element={<AdminDataManagementPage />}
                        />
                        <Route path="saglik" element={<SystemHealthPage />} />
                        <Route
                          path="bildirimler"
                          element={<AdminNotificationsPage />}
                        />
                      </Route>
                    </Route>
                  </Route>
                </Route>

                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </Suspense>
          </NotificationProvider>
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
