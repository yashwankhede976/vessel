import { Badge } from "../ui";
import type { BadgeVariant } from "../ui";

/**
 * Provenance label for a value or panel: REAL / SYNTHETIC / ESTIMATED /
 * FORECAST / UNKNOWN. Required by the platform rule that every value's nature is
 * clearly labelled. Reuses the shared Badge (no new visual language).
 */
export type DataKind =
  | "REAL"
  | "SYNTHETIC"
  | "ESTIMATED"
  | "FORECAST"
  | "UNKNOWN";

const VARIANT: Record<DataKind, BadgeVariant> = {
  REAL: "success",
  SYNTHETIC: "warning",
  ESTIMATED: "info",
  FORECAST: "accent",
  UNKNOWN: "neutral",
};

const TITLE: Record<DataKind, string> = {
  REAL: "Real observed/published data from a provider.",
  SYNTHETIC: "Synthetic / demo data — not real market data.",
  ESTIMATED: "Estimated where a direct measurement was unavailable.",
  FORECAST: "Model forecast for a future period.",
  UNKNOWN: "Not available.",
};

export default function DataLabel({
  kind,
  className,
}: {
  kind: DataKind;
  className?: string;
}) {
  return (
    <span title={TITLE[kind]} className={className}>
      <Badge variant={VARIANT[kind]}>{kind}</Badge>
    </span>
  );
}
