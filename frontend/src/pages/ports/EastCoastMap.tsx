import type { Port } from "../../api";
import "./EastCoastMap.css";

interface EastCoastMapProps {
  ports: Port[];
  selectedId: number | null;
  onSelect: (id: number) => void;
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

/**
 * A lightweight inline-SVG locator map of the East Coast India ports. It plots
 * each port at its coordinates and lets the user select one. This is a schematic
 * locator (no basemap tiles, no live data) — a full map library can replace it
 * later without changing the page contract.
 */
export default function EastCoastMap({ ports, selectedId, onSelect }: EastCoastMapProps) {
  return (
    <div className="ecmap">
      <svg
        viewBox={`0 0 ${VIEW.width} ${VIEW.height}`}
        className="ecmap__svg"
        role="img"
        aria-label="Locator map of East Coast India ports"
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

        {ports.map((port) => {
          const lat = Number(port.latitude);
          const lon = Number(port.longitude);
          if (Number.isNaN(lat) || Number.isNaN(lon)) return null;
          const { x, y } = project(lat, lon);
          const active = port.id === selectedId;
          return (
            <g
              key={port.id}
              className={active ? "ecmap__pin ecmap__pin--active" : "ecmap__pin"}
              transform={`translate(${x}, ${y})`}
              onClick={() => onSelect(port.id)}
              role="button"
              aria-label={`${port.name}${active ? " (selected)" : ""}`}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") onSelect(port.id);
              }}
            >
              <circle r={active ? 7 : 5} className="ecmap__dot" />
              <text x={10} y={4} className="ecmap__pinlabel">
                {port.name}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="ecmap__note">Schematic locator — no live traffic or congestion data.</p>
    </div>
  );
}
