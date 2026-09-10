/**
 * Central navigation definition — the single source of truth for the sidebar
 * and (conceptually) the route table. `icon` is a short glyph (dependency-free).
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
  { to: "/market", label: "Market Intelligence", icon: "≈", section: "overview" },
  { to: "/forecasts", label: "Freight Forecast", icon: "◪", section: "overview" },

  { to: "/vessels", label: "Vessels", icon: "⚓", section: "intelligence" },
  { to: "/ports", label: "Ports", icon: "⚑", section: "intelligence" },
  { to: "/cargo", label: "Cargo", icon: "▣", section: "intelligence" },
  { to: "/idle-vessels", label: "Idle Vessels", icon: "◍", section: "intelligence" },

  { to: "/decision", label: "Decision", icon: "◆", section: "decisions" },
  { to: "/chartering", label: "Chartering", icon: "✦", section: "decisions" },
  { to: "/optimizer", label: "Optimizer", icon: "◈", section: "decisions" },
  { to: "/scenarios", label: "Scenarios", icon: "⑃", section: "decisions" },
  { to: "/risk", label: "Risk", icon: "⚠", section: "decisions" },
  { to: "/alerts", label: "Alerts", icon: "!", section: "decisions" },

  { to: "/chatbot", label: "Chatbot", icon: "☉", section: "system" },
  { to: "/settings", label: "Settings", icon: "⚙", section: "system" },
];

export const SECTION_LABELS: Record<NavItem["section"], string> = {
  overview: "Overview",
  intelligence: "Intelligence",
  decisions: "Decisions",
  system: "System",
};
