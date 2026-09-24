import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import TopNav from "./TopNav";
import Sidebar from "./Sidebar";
import "./AppLayout.css";

const COLLAPSE_KEY = "vessel:sidebar-collapsed";

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === "1";
  } catch {
    return false;
  }
}

/** Application frame: top bar + responsive sidebar + routed content area. */
export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false); // mobile drawer
  const [collapsed, setCollapsed] = useState<boolean>(readCollapsed); // desktop
  const location = useLocation();

  // Close the mobile drawer whenever the route changes.
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  // Persist the desktop collapse preference.
  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  return (
    <div className="app-layout">
      <TopNav
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
        onToggleCollapse={() => setCollapsed((v) => !v)}
        collapsed={collapsed}
      />
      <div className="app-layout__body">
        <Sidebar
          open={sidebarOpen}
          collapsed={collapsed}
          onNavigate={() => setSidebarOpen(false)}
        />
        {sidebarOpen && (
          <div
            className="app-layout__backdrop"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}
        <main className="app-layout__content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
