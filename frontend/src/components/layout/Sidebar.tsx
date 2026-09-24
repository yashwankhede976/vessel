import { NavLink } from "react-router-dom";
import { NAV_ITEMS, SECTION_LABELS } from "../../navigation";
import type { NavItem } from "../../navigation";
import "./Sidebar.css";

interface SidebarProps {
  open: boolean;
  collapsed?: boolean;
  onNavigate: () => void;
}

const SECTION_ORDER: NavItem["section"][] = [
  "overview",
  "intelligence",
  "decisions",
  "system",
];

/** Left navigation. Collapses off-canvas on small screens; can be collapsed on
 *  desktop via the top-bar toggle for a full-width content view. */
export default function Sidebar({ open, collapsed = false, onNavigate }: SidebarProps) {
  const className = [
    "sidebar",
    open ? "sidebar--open" : "",
    collapsed ? "sidebar--collapsed" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <aside className={className} aria-label="Primary" aria-hidden={collapsed || undefined}>
      <nav className="sidebar__nav">
        {SECTION_ORDER.map((section) => {
          const items = NAV_ITEMS.filter((i) => i.section === section);
          if (items.length === 0) return null;
          return (
            <div key={section} className="sidebar__group">
              <p className="sidebar__group-label">{SECTION_LABELS[section]}</p>
              {items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    isActive ? "sidebar__link sidebar__link--active" : "sidebar__link"
                  }
                >
                  <span className="sidebar__icon" aria-hidden="true">
                    {item.icon}
                  </span>
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
