import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";
import { authApi, tokenStorage } from "../services/api/auth-service";
import { useAiStore } from "../stores/use-ai-store";
import { User } from "../types";

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  error: string | null;
  hasPermission: (permission: string) => boolean;
}

// ── Canonical role normalisation ───────────────────────────────────────────
// Backend may return 'SuperAdmin', 'super_admin', 'Super Admin', 'admin', …
// We normalise to lowercase snake_case at the point of ingestion so every
// other piece of code can rely on a single set of strings.
type CanonicalRole = "super_admin" | "admin" | "user" | "driver" | string;

function normaliseRole(raw: unknown): CanonicalRole {
  const s = String(raw ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "_");
  if (s === "superadmin" || s === "super_admin") return "super_admin";
  if (s === "admin") return "admin";
  if (s === "driver") return "driver";
  if (s === "user") return "user";
  return s; // pass through unknown roles unchanged
}

function mapUserData(userData: Record<string, unknown>): User {
  const email = (userData.email ||
    userData.kullanici_adi ||
    userData.username) as string | undefined;
  const rol = userData.rol as Record<string, unknown> | undefined;
  return {
    id: userData.id as number,
    email,
    username: email,
    full_name:
      ((userData.ad_soyad || userData.full_name) as string | undefined) ?? "",
    role: normaliseRole(rol?.ad ?? userData.rol ?? userData.role),
    is_active: (userData.aktif ?? userData.is_active) as boolean,
    last_login: (userData.son_giris as string | undefined) ?? undefined,
    created_at: (userData.created_at as string | undefined) ?? undefined,
    son_giris_ip: (userData.son_giris_ip as string | undefined) ?? undefined,
    sifre_degisim_tarihi:
      (userData.sifre_degisim_tarihi as string | undefined) ?? undefined,
    rol_yetkiler: rol?.yetkiler as Record<string, boolean> | undefined,
  };
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Token kontrolü ve kullanıcı bilgilerini getirme
  useEffect(() => {
    async function initAuth() {
      const token = tokenStorage.get();
      if (token) {
        try {
          const userData = await authApi.getMe();
          setUser(mapUserData(userData as Record<string, unknown>));
        } catch (err) {
          console.error("Session restoration failed", err);
          tokenStorage.remove();
          setUser(null);
        }
      }
      setIsLoading(false);
    }
    initAuth();
  }, []);

  const login = async (username: string, password: string) => {
    setError(null);
    setIsLoading(true);
    try {
      const response = await authApi.login(username, password);
      tokenStorage.set(response.access_token);
      const userData = await authApi.getMe();
      useAiStore.getState().clearHistory();
      setUser(mapUserData(userData as Record<string, unknown>));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Giriş yapılamadı";
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    useAiStore.getState().clearHistory();
    tokenStorage.remove();
    setUser(null);
    // Backend logout is best-effort (cookie deletion); don't block UI on DB availability
    authApi.logout().catch((e) => console.error("Backend logout failed", e));
  };

  const hasPermission = (permission: string): boolean => {
    if (!user) return false;

    // Prefer actual permissions from backend (rol_yetkiler) when available.
    // This reflects the real rol_yetkiler table rather than a hardcoded map.
    if (user.rol_yetkiler && Object.keys(user.rol_yetkiler).length > 0) {
      // Wildcard "*" = tüm yetkiler (super rol). Backend require_yetki de "*" kabul
      // eder; frontend de eşlemeli, aksi halde wildcard rolü specific yetkilerde kilitlenir.
      if (user.rol_yetkiler["*"] === true) return true;
      return user.rol_yetkiler[permission] === true;
    }

    const role = user.role ?? "";

    // Fallback for roles that don't carry explicit permission lists
    // (e.g. super_admin JWT without rol_yetkiler payload).
    if (role === "super_admin" || role === "admin") {
      if (permission.startsWith("system:")) return false;
      return true;
    }

    if (role === "bas_sofor") {
      return ["sefer:read", "sefer:onayla"].includes(permission);
    }

    if (role === "driver") {
      return ["sefer:read", "arac:read"].includes(permission);
    }

    if (role === "user") {
      return [
        "sefer:read",
        "sefer:write",
        "arac:read",
        "arac:write",
        "yakit:read",
        "yakit:write",
        "sofor:read",
        "sofor:write",
        "rapor:read",
        "lokasyon:read",
        "lokasyon:write",
        "dorse:read",
        "dorse:write",
      ].includes(permission);
    }

    return false;
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        error,
        hasPermission,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
