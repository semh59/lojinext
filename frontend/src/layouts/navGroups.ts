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
    ? { icon: ListChecks, label: t("nav.today", "Today"), path: "/today" }
    : { icon: BarChart3, label: t("dashboard.title", "Dashboard"), path: "/" };

  const groups: NavGroup[] = [
    { label: null, items: [home] },
    {
      label: t("nav.group.operations", "Operations"),
      items: [
        {
          icon: Activity,
          label: t("trips.title", "Trips"),
          path: "/trips",
        },
        { icon: Fuel, label: t("fuel.title", "Fuel"), path: "/fuel" },
        {
          icon: Wrench,
          label: t("nav.maintenance", "Maintenance"),
          path: "/maintenance",
        },
      ],
    },
    {
      label: t("nav.group.fleet", "Fleet"),
      items: [
        {
          icon: Truck,
          label: t("fleet.title", "Vehicles & Trailers"),
          path: "/fleet",
        },
        { icon: Users, label: t("drivers.title", "Drivers"), path: "/drivers" },
        {
          icon: MapPin,
          label: t("locations.title", "Locations"),
          path: "/locations",
        },
      ],
    },
    {
      label: t("nav.group.insights", "Insights"),
      items: [
        ...(canSeeInsights
          ? [
              {
                icon: Sparkles,
                label: t("nav.fleet_insights", "Fleet Insights"),
                path: "/insights/fleet",
              },
            ]
          : []),
        {
          icon: AlertTriangle,
          label: t("alerts.title", "Anomalies"),
          path: "/alerts",
        },
        {
          icon: BrainCircuit,
          label: t("predictions.title", "ML Predictions"),
          path: "/predictions",
        },
        {
          icon: GraduationCap,
          label: t("nav.coaching", "Coaching"),
          path: "/coaching",
        },
        ...(canSeeExecutive
          ? [
              {
                icon: LineChart,
                label: "Strategic Cockpit",
                path: "/executive",
              },
            ]
          : []),
        {
          icon: FileText,
          label: t("nav.reports", "Report Studio"),
          path: "/reports",
        },
        {
          icon: Route,
          label: t("nav.route_lab", "Route Lab"),
          path: "/route-lab",
        },
      ],
    },
  ];

  if (isAdmin) {
    groups.push({
      label: t("nav.group.system", "System"),
      items: [
        {
          icon: Shield,
          label: t("admin.title", "Administration"),
          path: "/admin",
        },
      ],
    });
  }

  return groups;
}
