import { ReactNode } from "react";
import { useAuth } from "../../context/AuthContext";

interface RequirePermissionProps {
  permission: string;
  children: ReactNode;
  fallback?: ReactNode;
}

/**
 * RequirePermission - Belirli bir yetkiye sahip kullanıcılar için bileşenleri gösterir.
 * Yetkisi olmayan kullanıcılara boş içerik veya belirtilen fallback bileşenini döner.
 */
export function RequirePermission({
  permission,
  children,
  fallback = null,
}: RequirePermissionProps) {
  const { hasPermission, isLoading } = useAuth();

  if (isLoading) return null;

  if (hasPermission(permission)) {
    return <>{children}</>;
  }

  return <>{fallback}</>;
}
