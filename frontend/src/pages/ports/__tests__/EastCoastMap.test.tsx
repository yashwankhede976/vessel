import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import EastCoastMap from "../EastCoastMap";
import type { Port, Vessel, VoyageRoute } from "../../../api";

const route = (over: Partial<VoyageRoute> = {}): VoyageRoute => ({
  id: 100, origin_name: "Australia", origin_country: "Australia",
  origin_port_name: "Newcastle (AU)", origin_latitude: "-32.927", origin_longitude: "151.78",
  destination_name: "Paradip", destination_country: "India",
  destination_latitude: "20.264", destination_longitude: "86.67",
  distance_nm: "6500.00", typical_transit_days: "20.00", drawable: true, ...over,
});

const port = (over: Partial<Port> = {}): Port => ({
  id: 1, name: "Paradip", country: "India", coast: "east_coast_india",
  coast_display: "East Coast (India)", unlocode: "INPRT", latitude: "20.26",
  longitude: "86.67", port_type: "seaport", port_type_display: "Seaport",
  berth_count: 3, created_at: "", updated_at: "", ...over,
});

const vessel = (over: Partial<Vessel> = {}): Vessel => ({
  id: 10, imo: "1000001", mmsi: "1", name: "Cape One", vessel_type: "capesize",
  vessel_type_display: "Capesize", dwt: "180000", loa: "292", beam: "45", draft: "18",
  flag: "PA", year_built: 2015, speed: "13", availability_status: "open",
  availability_status_display: "Open", open_date: null, metadata: {},
  latest_position: { latitude: "20.0", longitude: "86.5", sog: "12", cog: "220", heading: null, nav_status: "under way", timestamp: "2026-09-01T00:00:00Z" },
  created_at: "", updated_at: "", ...over,
});

describe("EastCoastMap", () => {
  it("plots ports and calls onSelect when a port is clicked", async () => {
    const onSelect = vi.fn();
    render(<EastCoastMap ports={[port(), port({ id: 2, name: "Dhamra", latitude: "20.79", longitude: "87.05" })]} selectedId={null} onSelect={onSelect} />);
    expect(screen.getByText("Paradip")).toBeInTheDocument();
    expect(screen.getByText("Dhamra")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Paradip/i }));
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it("overlays vessels and calls onSelectVessel when a vessel marker is clicked", async () => {
    const onSelectVessel = vi.fn();
    render(
      <EastCoastMap
        ports={[port()]}
        selectedId={null}
        onSelect={() => {}}
        vessels={[vessel()]}
        onSelectVessel={onSelectVessel}
      />,
    );
    const vesselMarker = screen.getByRole("button", { name: /Vessel Cape One/i });
    await userEvent.click(vesselMarker);
    expect(onSelectVessel).toHaveBeenCalled();
  });

  it("notes when there is no vessel overlay", () => {
    render(<EastCoastMap ports={[port()]} selectedId={null} onSelect={() => {}} />);
    expect(screen.getByText(/No live traffic overlay/i)).toBeInTheDocument();
  });

  it("draws a voyage route line and origin label when routes are supplied", async () => {
    const onSelectRoute = vi.fn();
    render(
      <EastCoastMap
        ports={[port()]}
        selectedId={null}
        onSelect={() => {}}
        routes={[route()]}
        onSelectRoute={onSelectRoute}
      />,
    );
    // Origin load-port label is rendered.
    expect(screen.getByText("Newcastle (AU)")).toBeInTheDocument();
    // The route count note appears.
    expect(screen.getByText(/1 voyage route/i)).toBeInTheDocument();
    // The route group is clickable.
    const routeEl = screen.getByRole("button", { name: /Route Australia to Paradip/i });
    await userEvent.click(routeEl);
    expect(onSelectRoute).toHaveBeenCalled();
  });

  it("does not draw non-drawable routes (missing coordinates)", () => {
    render(
      <EastCoastMap
        ports={[port()]}
        selectedId={null}
        onSelect={() => {}}
        routes={[route({ drawable: false, origin_latitude: null, origin_longitude: null })]}
      />,
    );
    expect(screen.queryByText(/voyage route/i)).not.toBeInTheDocument();
  });
});
