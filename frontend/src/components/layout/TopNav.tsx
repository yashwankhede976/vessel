import { Badge } from "../ui";
import "./TopNav.css";

interface TopNavProps {
  onToggleSidebar: () => void;
}

/** Top application bar: brand, menu toggle, and account/status area. */
export default function TopNav({ onToggleSidebar }: TopNavProps) {
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
