/**
 * Central navigation definition — the single source of truth for the sidebar
 * and the route table. `icon` is a short glyph (kept dependency-free); swap for
 * an icon component later if desired.
 */
export interface NavItem {
  to: string;
  label: string;
  icon: string;
  /** Grouping for the sidebar. */
  section: "overview" | "intelligence" | "decisions" | "system";
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: "▤", section: "overview" },
  { to: "/market", label: "Market", icon: "≈", section: "overview" },

  { to: "/vessels", label: "Vessels", icon: "⚓", section: "intelligence" },
  { to: "/ports", label: "Ports", icon: "⚑", section: "intelligence" },
  { to: "/cargo", label: "Cargo", icon: "▣", section: "intelligence" },
  { to: "/forecasts", label: "Forecasts", icon: "◪", section: "intelligence" },

  { to: "/optimizer", label: "Optimizer", icon: "◈", section: "decisions" },
  { to: "/recommendations", label: "Recommendations", icon: "✦", section: "decisions" },
  { to: "/scenarios", label: "Scenarios", icon: "⑃", section: "decisions" },
  { to: "/alerts", label: "Alerts", icon: "!", section: "decisions" },

  { to: "/settings", label: "Settings", icon: "⚙", section: "system" },
];

export const SECTION_LABELS: Record<NavItem["section"], string> = {
  overview: "Overview",
  intelligence: "Intelligence",
  decisions: "Decisions",
  system: "System",
};
