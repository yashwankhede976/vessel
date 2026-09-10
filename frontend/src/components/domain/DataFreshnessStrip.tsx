import { api, useApi } from "../../api";
import type { FreshnessEntry } from "../../api";
import { Badge } from "../ui";
import type { BadgeVariant } from "../ui";
import "./DataFreshnessStrip.css";

/**
 * A compact strip showing how current the key datasets are, so users know how
 * fresh a recommendation is. Consumes GET /system/data-freshness/. Degrades
 * quietly: if the endpoint is unavailable it renders nothing rather than error.
 */
const LEVEL_VARIANT: Record<FreshnessEntry["level"], BadgeVariant> = {
  FRESH: "success",
  STALE: "warning",
  VERY_STALE: "danger",
  UNKNOWN: "neutral",
};

const LEVEL_LABEL: Record<FreshnessEntry["level"], string> = {
  FRESH: "LIVE",
  STALE: "STALE",
  VERY_STALE: "VERY STALE",
  UNKNOWN: "UNKNOWN",
};

// Which datasets to surface in the strip and their display names.
const SHOWN: Array<{ dataset: string; label: string }> = [
  { dataset: "ais_positions", label: "AIS" },
  { dataset: "weather", label: "Weather" },
  { dataset: "trade", label: "Trade" },
  { dataset: "commodity_price", label: "Prices" },
  { dataset: "port_congestion", label: "Congestion" },
];

function ageText(entry: FreshnessEntry): string {
  if (entry.age_hours == null) return "no data";
  if (entry.age_hours < 1) return "just now";
  if (entry.age_hours < 24) return `${Math.round(entry.age_hours)}h ago`;
  return `${Math.round(entry.age_hours / 24)}d ago`;
}

export default function DataFreshnessStrip() {
  const state = useApi((signal) => api.system.dataFreshness(signal), []);

  if (state.loading || state.error || !state.data) {
    // Quiet degradation — never block the page on the freshness strip.
    return null;
  }

  const byDataset = new Map(state.data.datasets.map((d) => [d.dataset, d]));

  return (
    <div className="freshness-strip" aria-label="Data freshness">
      <span className="freshness-strip__title">Data freshness</span>
      {SHOWN.map(({ dataset, label }) => {
        const entry = byDataset.get(dataset);
        const level = entry?.level ?? "UNKNOWN";
        return (
          <span key={dataset} className="freshness-strip__item" title={entry ? ageText(entry) : "no data"}>
            <span className="freshness-strip__label">{label}</span>
            <Badge variant={LEVEL_VARIANT[level]} dot>
              {LEVEL_LABEL[level]}
            </Badge>
            <span className="freshness-strip__age">{entry ? ageText(entry) : "no data"}</span>
          </span>
        );
      })}
    </div>
  );
}
