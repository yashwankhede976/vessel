import { Navigate, type RouteObject } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import DashboardPage from "./pages/DashboardPage";
import PlaceholderPage from "./pages/PlaceholderPage";
import PortsPage from "./pages/ports/PortsPage";
import NotFoundPage from "./pages/NotFoundPage";

/**
 * Application route table. `/` redirects to the dashboard; all app routes
 * render inside AppLayout. Feature pages beyond the dashboard are placeholders
 * (no API data yet).
 */
export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", element: <DashboardPage /> },
      {
        path: "market",
        element: (
          <PlaceholderPage
            title="Market"
            description="Freight market overview, historical analytics, and rate context by lane."
            planned={[
              "Historical freight-rate trends and seasonality",
              "Bunker and commodity price context",
              "Lane comparison across origins",
            ]}
          />
        ),
      },
      {
        path: "vessels",
        element: (
          <PlaceholderPage
            title="Vessels"
            description="Vessel availability, tracking, and specifications."
            planned={[
              "Open/available tonnage by class",
              "Live positions and ETA",
              "Vessel–port compatibility",
            ]}
          />
        ),
      },
      { path: "ports", element: <PortsPage /> },
      {
        path: "cargo",
        element: (
          <PlaceholderPage
            title="Cargo"
            description="Cargo requirements and procurement planning."
            planned={[
              "Cargo requirements and laycan windows",
              "Total landed-cost comparison",
              "Multi-origin sourcing",
            ]}
          />
        ),
      },
      {
        path: "forecasts",
        element: (
          <PlaceholderPage
            title="Forecasts"
            description="Freight and ETA forecasts with confidence and explainability."
            planned={[
              "Short- and medium-term freight forecasts",
              "ETA predictions",
              "Explainable drivers and confidence bands",
            ]}
          />
        ),
      },
      {
        path: "optimizer",
        element: (
          <PlaceholderPage
            title="Optimizer"
            description="Sourcing, laycan, and contract-type optimization."
            planned={[
              "Multi-origin sourcing optimization",
              "Laycan optimization",
              "Spot vs short-term vs multi-voyage selection",
            ]}
          />
        ),
      },
      {
        path: "recommendations",
        element: (
          <PlaceholderPage
            title="Recommendations"
            description="Explainable decision recommendations with confidence and impact."
            planned={[
              "Market-entry timing",
              "Contract-type and alternative-port recommendations",
              "Explainability and audit trail",
            ]}
          />
        ),
      },
      {
        path: "alerts",
        element: (
          <PlaceholderPage
            title="Alerts"
            description="Material events: forecast shifts, congestion, weather, and risk."
            planned={[
              "Configurable alert rules",
              "Congestion and weather warnings",
              "Demurrage-risk breaches",
            ]}
          />
        ),
      },
      {
        path: "scenarios",
        element: (
          <PlaceholderPage
            title="Scenarios"
            description="What-if simulation against a base case."
            planned={[
              "Adjust bunker, congestion, demand, and timing",
              "Compare scenarios vs baseline",
              "Save and share scenarios",
            ]}
          />
        ),
      },
      {
        path: "settings",
        element: (
          <PlaceholderPage
            title="Settings"
            description="Application preferences and configuration."
            planned={[
              "Units, currency, and time zone",
              "Data source configuration",
              "Notification preferences",
            ]}
          />
        ),
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
