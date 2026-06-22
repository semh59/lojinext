import {
  Activity,
  AlertTriangle,
  BarChart3,
  BrainCircuit,
  FileText,
  Fuel,
  GraduationCap,
  LineChart,
  ListChecks,
  MapPin,
  Route,
  Shield,
  Sparkles,
  Truck,
  Users,
  Wrench,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  icon: LucideIcon;
  label: string;
  path: string;
}

export interface NavGroup {
  label: string | null;
  items: NavItem[];
}

export interface NavGroupsUser {
  role?: string | null;
}

const TRIAGE_ROLES = new Set(["admin", "super_admin", "fleet_manager"]);

/**
 * RV2.9 — Plan §6.1 sidebar grupları.
 *
 * Roller:
 * - admin / super_admin → tüm gruplar + Sistem
 * - fleet_manager → tüm gruplar (Sistem hariç)
 * - diğer → Panel + Operasyon + Filo + İçgörü (kısıtlı)
 */
export function buildNavGroups(
  user: NavGroupsUser | null | undefined,
  t: (key: string, fallback?: string) => string = (_k, fb) => fb ?? "",
): NavGroup[] {
  const role = user?.role ?? "";
  const isAdmin = role === "admin" || role === "super_admin";
  const canSeeTriage = TRIAGE_ROLES.has(role);
  const canSeeInsights = canSeeTriage;
  const canSeeExecutive = canSeeTriage;

  const home: NavItem = canSeeTriage
    ? { icon: ListChecks, label: "Bugün", path: "/today" }
    : { icon: BarChart3, label: t("dashboard.title", "Panel"), path: "/" };

  const groups: NavGroup[] = [
    { label: null, items: [home] },
    {
      label: "Operasyon",
      items: [
        {
          icon: Activity,
          label: t("dashboard.active_trips", "Seferler"),
          path: "/trips",
        },
        { icon: Fuel, label: t("fuel.title", "Yakıt"), path: "/fuel" },
        { icon: Wrench, label: "Bakım", path: "/maintenance" },
      ],
    },
    {
      label: "Filo",
      items: [
        { icon: Truck, label: "Araçlar & Dorseler", path: "/fleet" },
        { icon: Users, label: "Şoförler", path: "/drivers" },
        {
          icon: MapPin,
          label: t("locations.title", "Lokasyonlar"),
          path: "/locations",
        },
      ],
    },
    {
      label: "İçgörü",
      items: [
        ...(canSeeInsights
          ? [
              {
                icon: Sparkles,
                label: "Filo İçgörü",
                path: "/insights/fleet",
              },
            ]
          : []),
        {
          icon: AlertTriangle,
          label: t("alerts.title", "Anomaliler"),
          path: "/alerts",
        },
        {
          icon: BrainCircuit,
          label: t("predictions.title", "ML Tahminler"),
          path: "/predictions",
        },
        { icon: GraduationCap, label: "Koçluk", path: "/coaching" },
        ...(canSeeExecutive
          ? [
              {
                icon: LineChart,
                label: "Strategic Cockpit",
                path: "/executive",
              },
            ]
          : []),
        { icon: FileText, label: "Rapor Stüdyosu", path: "/reports" },
        { icon: Route, label: "Güzergah Lab", path: "/route-lab" },
      ],
    },
  ];

  if (isAdmin) {
    groups.push({
      label: "Sistem",
      items: [
        {
          icon: Shield,
          label: t("admin.title", "Sistem Yönetimi"),
          path: "/admin",
        },
      ],
    });
  }

  return groups;
}
