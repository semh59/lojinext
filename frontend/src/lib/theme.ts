/**
 * LojiNext Theme Configuration
 * Centralized design tokens for use in JS/TS (Framer Motion, Recharts, etc.)
 */

export const theme = {
  colors: {
    primary: {
      main: "#3B82F6",
      dark: "#1D4ED8",
      light: "#EFF6FF",
      deep: "#1E3A8A",
    },
    surface: {
      glass: "rgba(255, 255, 255, 0.7)",
      glassBorder: "rgba(255, 255, 255, 0.4)",
    },
    accent: "#10B981",
    background: "#F1F5F9", // Primary soft gray background
    dashboardBg: "#F4F7FE",
    text: {
      main: "#0F172A",
      secondary: "#475569",
    },
  },
  effects: {
    glassBlur: "12px",
    premiumShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.05)",
  },
};
