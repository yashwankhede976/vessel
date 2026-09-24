import { useId } from "react";
import "./LineChart.css";

/**
 * Dependency-free inline-SVG line chart. Renders one or more series plus an
 * optional shaded confidence band. Kept library-free (matching the hand-rolled
 * EastCoastMap) so it is lightweight and trivially testable; it plugs into
 * ChartContainer as `children` without changing that contract.
 */
export interface ChartPoint {
  x: number; // numeric x (e.g. day index or epoch)
  y: number;
}
export interface ChartSeries {
  name: string;
  points: ChartPoint[];
  color?: string;
  dashed?: boolean;
}
export interface ConfidenceBand {
  lower: ChartPoint[];
  upper: ChartPoint[];
  color?: string;
}

interface LineChartProps {
  series: ChartSeries[];
  band?: ConfidenceBand;
  height?: number;
  yLabel?: string;
  xLabels?: string[]; // optional tick labels aligned to unique x values
  emptyMessage?: string;
}

const PAD = { top: 12, right: 16, bottom: 28, left: 44 };
const DEFAULT_COLORS = ["#d9772b", "#6f8b52", "#2f6fb0", "#c1443a"];

export default function LineChart({
  series,
  band,
  height = 280,
  yLabel,
  xLabels,
  emptyMessage = "No data to plot.",
}: LineChartProps) {
  const clipId = useId();
  const allPoints = [
    ...series.flatMap((s) => s.points),
    ...(band ? [...band.lower, ...band.upper] : []),
  ];
  if (allPoints.length === 0) {
    return <p className="linechart__empty">{emptyMessage}</p>;
  }

  const width = 640; // viewBox width; SVG scales responsively
  const xs = allPoints.map((p) => p.x);
  const ys = allPoints.map((p) => p.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;

  const plotW = width - PAD.left - PAD.right;
  const plotH = height - PAD.top - PAD.bottom;

  const sx = (x: number) => PAD.left + ((x - minX) / spanX) * plotW;
  const sy = (y: number) => PAD.top + plotH - ((y - minY) / spanY) * plotH;

  const toPath = (pts: ChartPoint[]) =>
    pts.map((p, i) => `${i === 0 ? "M" : "L"} ${sx(p.x).toFixed(1)} ${sy(p.y).toFixed(1)}`).join(" ");

  const bandPath = band
    ? `${toPath(band.upper)} L ${sx(band.lower[band.lower.length - 1].x).toFixed(1)} ${sy(
        band.lower[band.lower.length - 1].y,
      ).toFixed(1)} ${band.lower
        .slice()
        .reverse()
        .map((p) => `L ${sx(p.x).toFixed(1)} ${sy(p.y).toFixed(1)}`)
        .join(" ")} Z`
    : null;

  // Y-axis ticks (4 divisions).
  const yTicks = Array.from({ length: 4 }, (_, i) => minY + (spanY * i) / 3);
  // X-axis tick positions from unique sorted x values.
  const uniqueX = Array.from(new Set(xs)).sort((a, b) => a - b);

  return (
    <svg
      className="linechart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={yLabel ? `Line chart of ${yLabel}` : "Line chart"}
      preserveAspectRatio="none"
    >
      <defs>
        <clipPath id={clipId}>
          <rect x={PAD.left} y={PAD.top} width={plotW} height={plotH} />
        </clipPath>
      </defs>

      {/* Y grid + labels */}
      {yTicks.map((t, i) => (
        <g key={i}>
          <line
            x1={PAD.left}
            x2={width - PAD.right}
            y1={sy(t)}
            y2={sy(t)}
            className="linechart__grid"
          />
          <text x={PAD.left - 6} y={sy(t) + 3} className="linechart__ytick" textAnchor="end">
            {t.toFixed(t >= 100 ? 0 : 1)}
          </text>
        </g>
      ))}

      {/* Confidence band */}
      {bandPath && (
        <path
          d={bandPath}
          className="linechart__band"
          fill={band?.color ?? "#d9772b"}
          clipPath={`url(#${clipId})`}
        />
      )}

      {/* Series */}
      {series.map((s, i) => (
        <path
          key={s.name}
          d={toPath(s.points)}
          fill="none"
          stroke={s.color ?? DEFAULT_COLORS[i % DEFAULT_COLORS.length]}
          strokeWidth={2}
          strokeDasharray={s.dashed ? "5 4" : undefined}
          clipPath={`url(#${clipId})`}
        />
      ))}

      {/* X tick labels */}
      {xLabels &&
        uniqueX.map((x, i) =>
          xLabels[i] ? (
            <text
              key={x}
              x={sx(x)}
              y={height - 8}
              className="linechart__xtick"
              textAnchor="middle"
            >
              {xLabels[i]}
            </text>
          ) : null,
        )}
    </svg>
  );
}
