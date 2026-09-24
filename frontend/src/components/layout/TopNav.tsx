import { Badge } from "../ui";
import { useTheme, THEMES, THEME_META } from "../../lib/theme";
import "./TopNav.css";

interface TopNavProps {
  /** Toggles the off-canvas drawer on mobile. */
  onToggleSidebar: () => void;
  /** Toggles the collapsed sidebar on desktop (full-width content). */
  onToggleCollapse: () => void;
  /** Whether the desktop sidebar is currently collapsed. */
  collapsed: boolean;
}

/** Top application bar: brand, menu/collapse toggles, theme switcher, account. */
export default function TopNav({ onToggleSidebar, onToggleCollapse, collapsed }: TopNavProps) {
  const [theme, setTheme] = useTheme();

  return (
    <header className="topnav">
      <div className="topnav__left">
        <button
          type="button"
          className="topnav__menu"
          aria-label="Toggle navigation"
          onClick={onToggleSidebar}
        >
          ☰
        </button>
        <button
          type="button"
          className="topnav__collapse"
          aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          aria-pressed={collapsed}
          title={collapsed ? "Expand navigation" : "Collapse navigation"}
          onClick={onToggleCollapse}
        >
          {collapsed ? "»" : "«"}
        </button>
        <div className="topnav__brand">
          <span className="topnav__mark" aria-hidden="true">
            ⚓
          </span>
          <span className="topnav__name">Vessel</span>
          <Badge variant="accent">Beta</Badge>
        </div>
      </div>

      <div className="topnav__right">
        <span className="topnav__hint">East Coast India · Dry Bulk</span>

        <div className="topnav__themes" role="group" aria-label="Theme">
          {THEMES.map((t) => (
            <button
              key={t}
              type="button"
              className={t === theme ? "topnav__theme topnav__theme--active" : "topnav__theme"}
              aria-label={`${THEME_META[t].label} theme`}
              aria-pressed={t === theme}
              title={THEME_META[t].label}
              onClick={() => setTheme(t)}
            >
              {THEME_META[t].glyph}
            </button>
          ))}
        </div>

        <button type="button" className="topnav__icon-btn" aria-label="Notifications">
          ◔
        </button>
        <div className="topnav__avatar" aria-hidden="true">
          VC
        </div>
      </div>
    </header>
  );
}
