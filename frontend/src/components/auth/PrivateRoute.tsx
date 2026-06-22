import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

export function PrivateRoute({
  requiredPermission,
}: {
  requiredPermission?: string;
}) {
  const { isAuthenticated, isLoading, hasPermission } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-base">
        <div className="flex flex-col items-center gap-6">
          <div className="w-10 h-10 border-[3px] border-accent/20 border-t-accent rounded-full animate-spin" />
          <span className="text-secondary font-bold text-xs uppercase tracking-[0.2em] animate-pulse text-center">
            Oturum Kontrol Ediliyor
          </span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  if (requiredPermission && !hasPermission(requiredPermission)) {
    return <Navigate to="/trips" replace />;
  }

  return <Outlet />;
}
