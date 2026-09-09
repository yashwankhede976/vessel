import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import TopNav from "./TopNav";
import Sidebar from "./Sidebar";
import "./AppLayout.css";

/** Application frame: top bar + responsive sidebar + routed content area. */
export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  // Close the mobile drawer whenever the route changes.
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  return (
    <div className="app-layout">
      <TopNav onToggleSidebar={() => setSidebarOpen((v) => !v)} />
      <div className="app-layout__body">
        <Sidebar open={sidebarOpen} onNavigate={() => setSidebarOpen(false)} />
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
