import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, useRoutes } from "react-router-dom";
import { routes } from "../routes";

// The dashboard and several pages fetch on mount; stub the whole api so routing
// tests are isolated from network behaviour.
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  const never = () => new Promise(() => {}); // pending — keeps pages in loading
  return {
    ...actual,
    api: {
      ports: { list: never },
      routes: { list: never },
      vessels: { list: never, available: never },
      alerts: { list: never },
      analytics: {
        marketPressure: never, freightForecast: never, fixWait: never,
        spotVsContract: never,
      },
      decision: { evaluate: never },
      chat: { send: never, reset: never },
      system: { dataFreshness: never, externalServices: never },
    },
  };
});

function RoutedApp() {
  return useRoutes(routes);
}

describe("routing", () => {
  it("renders the app shell with the sidebar navigation", () => {
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <RoutedApp />
      </MemoryRouter>,
    );
    // Sidebar nav links from navigation.ts (scoped to nav links, since some
    // labels like "Dashboard" also appear as the page title).
    expect(screen.getByRole("link", { name: /Chartering/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Risk/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Alerts/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Market Intelligence/i })).toBeInTheDocument();
  });

  it("shows the not-found page for an unknown route", () => {
    render(
      <MemoryRouter initialEntries={["/nope"]}>
        <RoutedApp />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Page not found/i)).toBeInTheDocument();
  });

  it("mounts the Chartering page at its route", () => {
    render(
      <MemoryRouter initialEntries={["/chartering"]}>
        <RoutedApp />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("button", { name: /Get recommendation/i }),
    ).toBeInTheDocument();
  });
});
