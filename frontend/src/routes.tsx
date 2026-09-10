import { Navigate, type RouteObject } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import DashboardPage from "./pages/DashboardPage";
import DecisionPage from "./pages/DecisionPage";
import MarketIntelligencePage from "./pages/MarketIntelligencePage";
import FreightForecastPage from "./pages/FreightForecastPage";
import VesselsPage from "./pages/VesselsPage";
import PortsPage from "./pages/ports/PortsPage";
import CargoPage from "./pages/CargoPage";
import IdleVesselsPage from "./pages/IdleVesselsPage";
import CharteringPage from "./pages/CharteringPage";
import OptimizerPage from "./pages/OptimizerPage";
import ScenariosPage from "./pages/ScenariosPage";
import RiskPage from "./pages/RiskPage";
import AlertsPage from "./pages/AlertsPage";
import ChatbotPage from "./pages/ChatbotPage";
import SettingsPage from "./pages/SettingsPage";
import NotFoundPage from "./pages/NotFoundPage";

/**
 * Application route table. `/` redirects to the dashboard; all app routes render
 * inside AppLayout. Every route consumes the real backend APIs via the api
 * client (see src/api). Paths align with navigation.ts.
 */
export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", element: <DashboardPage /> },
      { path: "decision", element: <DecisionPage /> },
      { path: "market", element: <MarketIntelligencePage /> },
      { path: "forecasts", element: <FreightForecastPage /> },
      { path: "vessels", element: <VesselsPage /> },
      { path: "ports", element: <PortsPage /> },
      { path: "cargo", element: <CargoPage /> },
      { path: "idle-vessels", element: <IdleVesselsPage /> },
      { path: "chartering", element: <CharteringPage /> },
      { path: "optimizer", element: <OptimizerPage /> },
      { path: "scenarios", element: <ScenariosPage /> },
      { path: "risk", element: <RiskPage /> },
      { path: "alerts", element: <AlertsPage /> },
      { path: "chatbot", element: <ChatbotPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
