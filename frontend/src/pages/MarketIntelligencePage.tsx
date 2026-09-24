import { useState } from "react";
import PageHeader from "../components/layout/PageHeader";
import { Card, EmptyState, ErrorState, FormField, Loading } from "../components/ui";
import { DataFreshnessStrip, DataLabel, ScoreBar, StatTile } from "../components/domain";
import { api, ApiError } from "../api";
import type { MarketPressureResult } from "../api";
import { humanize } from "../lib/format";
import "./MarketIntelligencePage.css";

/**
 * Market Intelligence: the Freight Market Pressure Index (0–100) with its full
 * factor breakdown, computed by the backend market-pressure engine. Inputs are
 * adjustable so a user can explore the current market read. All values are
 * ESTIMATED signals fed to a deterministic index (labelled accordingly).
 */
const BAND_TONE: Record<string, "success" | "info" | "warning" | "danger"> = {
  VERY_WEAK: "success",
  WEAK: "success",
  NEUTRAL: "info",
  TIGHT: "warning",
  EXTREMELY_TIGHT: "danger",
};

const SIGNAL_FIELDS: Array<{ key: keyof SignalState; label: string; max: number; hint: string }> = [
  { key: "vessel_supply", label: "Vessel supply (availability)", max: 1, hint: "0 = scarce, 1 = abundant" },
  { key: "cargo_demand", label: "Cargo demand", max: 1, hint: "0..1 demand intensity" },
  { key: "ton_mile_demand", label: "Ton-mile demand", max: 1, hint: "0..1 proxy" },
  { key: "port_congestion", label: "Port congestion", max: 100, hint: "0..100 score" },
  { key: "freight_volatility", label: "Freight volatility", max: 1, hint: "0..1" },
  { key: "bunker", label: "Bunker pressure", max: 1, hint: "0..1 vs reference" },
  { key: "seasonality", label: "Seasonality", max: 1, hint: "0..1 seasonal factor" },
];

interface SignalState {
  vessel_supply: string;
  cargo_demand: string;
  ton_mile_demand: string;
  port_congestion: string;
  freight_volatility: string;
  bunker: string;
  seasonality: string;
}

const INITIAL: SignalState = {
  vessel_supply: "0.35",
  cargo_demand: "0.75",
  ton_mile_demand: "0.7",
  port_congestion: "60",
  freight_volatility: "0.5",
  bunker: "0.6",
  seasonality: "0.4",
};

export default function MarketIntelligencePage() {
  const [signals, setSignals] = useState<SignalState>(INITIAL);
  const [result, setResult] = useState<MarketPressureResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const setField = (key: keyof SignalState) => (value: string) =>
    setSignals((s) => ({ ...s, [key]: value }));

  const compute = async () => {
    setLoading(true);
    setError(null);
    try {
      const input: Record<string, number> = {};
      for (const { key } of SIGNAL_FIELDS) {
        const raw = signals[key];
        if (raw !== "" && raw != null) input[key] = Number(raw);
      }
      const res = await api.analytics.marketPressure(input);
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError("network", "Unexpected error."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Market Intelligence"
        description="Freight Market Pressure Index for East Coast India dry-bulk — a transparent 0–100 read of how tight the market is, with a full factor breakdown."
        actions={
          <button className="btn btn--primary" onClick={compute} disabled={loading}>
            {loading ? "Computing…" : "Compute index"}
          </button>
        }
      />

      <DataFreshnessStrip />

      <div className="market-layout">
        <Card title="Market signals" subtitle="Adjustable inputs (ESTIMATED)">
          <p className="market-hint">
            <DataLabel kind="ESTIMATED" /> These are analyst signals fed to the
            deterministic index; blank a field to exclude it (its weight is
            redistributed).
          </p>
          <div className="market-form">
            {SIGNAL_FIELDS.map((f) => (
              <FormField
                key={f.key}
                label={f.label}
                hint={f.hint}
                type="number"
                value={signals[f.key]}
                onChange={setField(f.key)}
              />
            ))}
          </div>
        </Card>

        <div className="market-result">
          {loading ? (
            <Card><Loading fill label="Computing market pressure…" /></Card>
          ) : error ? (
            <Card><ErrorState onRetry={compute} message={error.displayMessage} /></Card>
          ) : !result ? (
            <Card>
              <EmptyState
                icon="≈"
                title="No index yet"
                message="Set your market signals and compute the index to see the current pressure read and its drivers."
              />
            </Card>
          ) : (
            <>
              <StatTile
                label="Freight Market Pressure Index"
                value={result.index.toFixed(1)}
                note={`Classification: ${humanize(result.classification)}`}
              />
              <Card title="Factor breakdown" subtitle="Contribution to the 0–100 index">
                {result.factors.map((f) => (
                  <ScoreBar
                    key={f.factor}
                    label={humanize(f.factor)}
                    value={f.available ? f.contribution : null}
                    max={100}
                    unknown={!f.available}
                    tone={BAND_TONE[result.classification] ?? "accent"}
                    note={f.note}
                  />
                ))}
                {result.missing_factors.length > 0 && (
                  <p className="market-missing">
                    Excluded (no data): {result.missing_factors.map(humanize).join(", ")}
                  </p>
                )}
              </Card>
            </>
          )}
        </div>
      </div>
    </>
  );
}
