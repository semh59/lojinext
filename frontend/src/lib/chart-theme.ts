/**
 * Shared Recharts style tokens.
 * CSS variables are resolved by the browser at render time,
 * so dark/light mode switching works automatically.
 */
export const chartTheme = {
  grid: {
    strokeDasharray: "3 3" as const,
    stroke: "var(--border)",
    opacity: 0.6,
  },
  tick: {
    fill: "var(--text-secondary)",
    fontSize: 11,
  },
  tickSmall: {
    fill: "var(--text-secondary)",
    fontSize: 10,
  },
  tooltip: {
    contentStyle: {
      backgroundColor: "var(--bg-surface)",
      border: "1px solid var(--border)",
      borderRadius: "8px",
      padding: "10px 14px",
      boxShadow:
        "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
    },
    labelStyle: {
      color: "var(--text-secondary)",
      fontSize: "10px",
      fontWeight: 600,
      letterSpacing: "0.05em",
      textTransform: "uppercase" as const,
      marginBottom: "4px",
    },
    itemStyle: {
      color: "var(--text-primary)",
      fontSize: "12px",
      fontWeight: 700,
    },
  },
  colors: {
    accent: "var(--accent)",
    success: "var(--success)",
    danger: "var(--danger)",
    warning: "var(--warning)",
    info: "var(--info)",
    border: "var(--border)",
    secondary: "var(--text-secondary)",
  },
} as const;
