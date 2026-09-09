import { NavLink } from "react-router-dom";
import { NAV_ITEMS, SECTION_LABELS } from "../../navigation";
import type { NavItem } from "../../navigation";
import "./Sidebar.css";

interface SidebarProps {
  open: boolean;
  onNavigate: () => void;
}

const SECTION_ORDER: NavItem["section"][] = [
  "overview",
  "intelligence",
  "decisions",
  "system",
];

/** Left navigation. Collapses off-canvas on small screens. */
export default function Sidebar({ open, onNavigate }: SidebarProps) {
  return (
    <aside className={open ? "sidebar sidebar--open" : "sidebar"} aria-label="Primary">
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
