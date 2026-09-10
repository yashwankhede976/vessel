import type { Port, Vessel, VoyageRoute } from "../../api";
import "./EastCoastMap.css";

/** Optional per-port congestion status for the map overlay. */
export interface PortStatus {
  portId: number;
  level: "LOW" | "MEDIUM" | "HIGH" | "SEVERE" | "UNKNOWN";
}

interface EastCoastMapProps {
  ports: Port[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  /** Optional vessel overlay (plotted from latest AIS position). */
  vessels?: Vessel[];
  /** Optional per-port congestion status. */
  portStatus?: PortStatus[];
  /** Optional vessel click handler (opens contextual details). */
  onSelectVessel?: (vessel: Vessel) => void;
  /** Optional voyage routes (origin -> destination) to draw as lines. When
   * supplied, the map auto-fits its bounds to include the route endpoints so
   * overseas origins are visible; otherwise it frames the East Coast of India. */
  routes?: VoyageRoute[];
  /** Optional route click handler. */
  onSelectRoute?: (route: VoyageRoute) => void;
}

type Bounds = { minLat: number; maxLat: number; minLon: number; maxLon: number };

// Default bounds framing the East Coast of India (with padding).
const DEFAULT_BOUNDS: Bounds = { minLat: 16.5, maxLat: 23.0, minLon: 82.0, maxLon: 89.5 };
const VIEW = { width: 320, height: 440, pad: 28 };

const num = (v: string | number | null | undefined): number | null => {
  if (v == null || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isNaN(n) ? null : n;
};

/** A route is renderable only when both endpoints resolved to coordinates. */
function routeCoords(r: VoyageRoute) {
  const oLat = num(r.origin_latitude);
  const oLon = num(r.origin_longitude);
  const dLat = num(r.destination_latitude);
  const dLon = num(r.destination_longitude);
  if (oLat == null || oLon == null || dLat == null || dLon == null) return null;
  return { oLat, oLon, dLat, dLon };
}

/** Compute display bounds: if any routes are drawable, expand to include their
 * endpoints (plus a margin); otherwise use the East-Coast default. */
function computeBounds(ports: Port[], routes: VoyageRoute[]): Bounds {
  const drawable = routes.map(routeCoords).filter((c): c is NonNullable<typeof c> => c !== null);
  if (drawable.length === 0) return DEFAULT_BOUNDS;

  const lats: number[] = [];
  const lons: number[] = [];
  for (const c of drawable) {
    lats.push(c.oLat, c.dLat);
    lons.push(c.oLon, c.dLon);
  }
  // Include the destination ports too so labels stay in frame.
  for (const p of ports) {
    const lat = num(p.latitude);
    const lon = num(p.longitude);
    if (lat != null && lon != null) { lats.push(lat); lons.push(lon); }
  }
  const marginLat = Math.max(2, (Math.max(...lats) - Math.min(...lats)) * 0.08);
  const marginLon = Math.max(2, (Math.max(...lons) - Math.min(...lons)) * 0.08);
  return {
    minLat: Math.min(...lats) - marginLat,
    maxLat: Math.max(...lats) + marginLat,
    minLon: Math.min(...lons) - marginLon,
    maxLon: Math.max(...lons) + marginLon,
  };
}

function makeProject(bounds: Bounds) {
  const { minLat, maxLat, minLon, maxLon } = bounds;
  const { width, height, pad } = VIEW;
  const lonSpan = maxLon - minLon || 1;
  const latSpan = maxLat - minLat || 1;
  return (lat: number, lon: number) => {
    const x = pad + ((lon - minLon) / lonSpan) * (width - 2 * pad);
    // Latitude increases upward, so invert the y axis.
    const y = pad + ((maxLat - lat) / latSpan) * (height - 2 * pad);
    return { x, y };
  };
}

const makeInBounds = (b: Bounds) => (lat: number, lon: number) =>
  lat >= b.minLat && lat <= b.maxLat && lon >= b.minLon && lon <= b.maxLon;

const CONGESTION_CLASS: Record<PortStatus["level"], string> = {
  LOW: "ecmap__dot--low",
  MEDIUM: "ecmap__dot--medium",
  HIGH: "ecmap__dot--high",
  SEVERE: "ecmap__dot--severe",
  UNKNOWN: "",
};

/**
 * A lightweight inline-SVG locator map of the East Coast India ports. Plots each
 * port at its coordinates (optionally coloured by congestion), overlays vessel
 * positions when supplied, and lets the user select a port or vessel. This is a
 * schematic locator (no basemap tiles) — a full map library (MapLibre, see
 * VITE_MAP_* env) can replace it later without changing the page contract.
 */
export default function EastCoastMap({
  ports,
  selectedId,
  onSelect,
  vessels = [],
  portStatus = [],
  onSelectVessel,
  routes = [],
  onSelectRoute,
}: EastCoastMapProps) {
  const drawableRoutes = routes.filter((r) => r.drawable && routeCoords(r) !== null);
  const bounds = computeBounds(ports, drawableRoutes);
  const project = makeProject(bounds);
  const inBounds = makeInBounds(bounds);
  const hasRoutes = drawableRoutes.length > 0;

  const statusByPort = new Map(portStatus.map((s) => [s.portId, s.level]));
  const plottableVessels = vessels.filter((v) => {
    const p = v.latest_position;
    if (!p) return false;
    const lat = Number(p.latitude);
    const lon = Number(p.longitude);
    return !Number.isNaN(lat) && !Number.isNaN(lon) && inBounds(lat, lon);
  });

  return (
    <div className="ecmap">
      <svg
        viewBox={`0 0 ${VIEW.width} ${VIEW.height}`}
        className="ecmap__svg"
        role="img"
        aria-label="Locator map of East Coast India ports and vessels"
      >
        <defs>
          <marker
            id="ecmap-arrow"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M0,0 L10,5 L0,10 z" className="ecmap__route-arrowhead" />
          </marker>
        </defs>

        {/* Sea backdrop + a suggestive coastline (schematic, not survey-grade).
            The stylised coastline only makes sense at the East-Coast framing, so
            it is hidden when the map auto-fits to overseas voyage routes. */}
        <rect x="0" y="0" width={VIEW.width} height={VIEW.height} className="ecmap__sea" />
        {!hasRoutes && (
          <path
            className="ecmap__coast"
            d="M40,20 C120,70 150,150 160,230 C168,300 200,370 250,420"
            fill="none"
          />
        )}
        <text x={VIEW.pad} y={16} className="ecmap__label">
          {hasRoutes ? "Voyage routes → East Coast India" : "East Coast, India"}
        </text>

        {/* Voyage routes: origin -> destination lines with a direction arrow. */}
        {drawableRoutes.map((r) => {
          const c = routeCoords(r)!;
          const o = project(c.oLat, c.oLon);
          const d = project(c.dLat, c.dLon);
          return (
            <g
              key={`r-${r.id}`}
              className="ecmap__route"
              onClick={() => onSelectRoute?.(r)}
              role={onSelectRoute ? "button" : undefined}
              tabIndex={onSelectRoute ? 0 : undefined}
              aria-label={`Route ${r.origin_name} to ${r.destination_name}`}
              onKeyDown={(e) => {
                if (onSelectRoute && (e.key === "Enter" || e.key === " ")) onSelectRoute(r);
              }}
            >
              <line
                x1={o.x}
                y1={o.y}
                x2={d.x}
                y2={d.y}
                className="ecmap__route-line"
                markerEnd="url(#ecmap-arrow)"
              />
              {/* Origin (load port) marker + label. */}
              <circle cx={o.x} cy={o.y} r={3.5} className="ecmap__route-origin" />
              <text x={o.x + 6} y={o.y - 4} className="ecmap__route-label">
                {r.origin_port_name ?? r.origin_name}
              </text>
            </g>
          );
        })}

        {/* Vessel overlay (drawn under the port pins). */}
        {plottableVessels.map((v) => {
          const p = v.latest_position!;
          const { x, y } = project(Number(p.latitude), Number(p.longitude));
          return (
            <g
              key={`v-${v.id}`}
              className="ecmap__vessel"
              transform={`translate(${x}, ${y})`}
              onClick={() => onSelectVessel?.(v)}
              role={onSelectVessel ? "button" : undefined}
              aria-label={`Vessel ${v.name}`}
              tabIndex={onSelectVessel ? 0 : undefined}
              onKeyDown={(e) => {
                if (onSelectVessel && (e.key === "Enter" || e.key === " ")) onSelectVessel(v);
              }}
            >
              <path d="M0,-4 L3,4 L-3,4 Z" className="ecmap__vessel-mark" />
            </g>
          );
        })}

        {ports.map((port) => {
          const lat = Number(port.latitude);
          const lon = Number(port.longitude);
          if (Number.isNaN(lat) || Number.isNaN(lon)) return null;
          const { x, y } = project(lat, lon);
          const active = port.id === selectedId;
          const level = statusByPort.get(port.id);
          const congestionClass = level ? CONGESTION_CLASS[level] : "";
          return (
            <g
              key={port.id}
              className={active ? "ecmap__pin ecmap__pin--active" : "ecmap__pin"}
              transform={`translate(${x}, ${y})`}
              onClick={() => onSelect(port.id)}
              role="button"
              aria-label={`${port.name}${active ? " (selected)" : ""}${level ? `, congestion ${level}` : ""}`}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") onSelect(port.id);
              }}
            >
              <circle r={active ? 7 : 5} className={`ecmap__dot ${congestionClass}`} />
              <text x={10} y={4} className="ecmap__pinlabel">
                {port.name}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="ecmap__note">
        Schematic locator.
        {hasRoutes ? ` ${drawableRoutes.length} voyage route(s).` : ""}
        {vessels.length > 0 ? ` ${plottableVessels.length} vessel(s) in view.` : (!hasRoutes ? " No live traffic overlay." : "")}
      </p>
    </div>
  );
}
