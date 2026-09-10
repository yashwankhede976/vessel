import type { Port, Vessel } from "../../api";
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
}

// Geographic bounds framing the East Coast of India (with padding).
const BOUNDS = { minLat: 16.5, maxLat: 23.0, minLon: 82.0, maxLon: 89.5 };
const VIEW = { width: 320, height: 440, pad: 28 };

function project(lat: number, lon: number): { x: number; y: number } {
  const { minLat, maxLat, minLon, maxLon } = BOUNDS;
  const { width, height, pad } = VIEW;
  const x = pad + ((lon - minLon) / (maxLon - minLon)) * (width - 2 * pad);
  // Latitude increases upward, so invert the y axis.
  const y = pad + ((maxLat - lat) / (maxLat - minLat)) * (height - 2 * pad);
  return { x, y };
}

const inBounds = (lat: number, lon: number) =>
  lat >= BOUNDS.minLat && lat <= BOUNDS.maxLat && lon >= BOUNDS.minLon && lon <= BOUNDS.maxLon;

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
}: EastCoastMapProps) {
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
        {/* Sea backdrop + a suggestive coastline (schematic, not survey-grade). */}
        <rect x="0" y="0" width={VIEW.width} height={VIEW.height} className="ecmap__sea" />
        <path
          className="ecmap__coast"
          d="M40,20 C120,70 150,150 160,230 C168,300 200,370 250,420"
          fill="none"
        />
        <text x={VIEW.pad} y={16} className="ecmap__label">
          East Coast, India
        </text>

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
        {vessels.length > 0 ? ` ${plottableVessels.length} vessel(s) in view.` : " No live traffic overlay."}
      </p>
    </div>
  );
}
