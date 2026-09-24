import { useState } from "react";
import PageHeader from "../components/layout/PageHeader";
import { Badge, Card, EmptyState, ErrorState, FormField, Loading } from "../components/ui";
import type { BadgeVariant } from "../components/ui";
import { ScoreBar, StatTile } from "../components/domain";
import { api, ApiError } from "../api";
import type { RiskResult } from "../api";
import { humanize } from "../lib/format";
import "./RiskPage.css";

/**
 * Risk Dashboard: the unified risk engine (0–100 overall score + factor
 * breakdown). Signals left blank stay UNKNOWN — the backend never invents a
 * value, and the UI shows UNKNOWN factors explicitly rather than as zero.
 */
const FIELDS: Array<{ key: keyof SignalState; label: string; max: number; hint: string }> = [
  { key: "freight_volatility", label: "Freight volatility", max: 1, hint: "0..1" },
  { key: "port_congestion", label: "Port congestion", max: 100, hint: "0..100" },
  { key: "weather_risk", label: "Weather risk", max: 1, hint: "0..1" },
  { key: "eta_delay_probability", label: "ETA delay probability", max: 1, hint: "0..1" },
  { key: "expected_demurrage_cost", label: "Expected demurrage (cost)", max: 500000, hint: "currency" },
  { key: "commodity_volatility", label: "Commodity volatility", max: 1, hint: "0..1" },
  { key: "fx_volatility", label: "FX volatility", max: 1, hint: "0..1" },
  { key: "geopolitical_risk", label: "Geopolitical risk", max: 1, hint: "0..1 (reliable data only)" },
];

interface SignalState {
  freight_volatility: string;
  port_congestion: string;
  weather_risk: string;
  eta_delay_probability: string;
  expected_demurrage_cost: string;
  commodity_volatility: string;
  fx_volatility: string;
  geopolitical_risk: string;
}

const EMPTY: SignalState = {
  freight_volatility: "0.6",
  port_congestion: "70",
  weather_risk: "0.4",
  eta_delay_probability: "0.3",
  expected_demurrage_cost: "",
  commodity_volatility: "",
  fx_volatility: "",
  geopolitical_risk: "",
};

const levelVariant = (level: string): BadgeVariant =>
  level === "HIGH" ? "danger" : level === "MEDIUM" ? "warning" : level === "LOW" ? "success" : "neutral";

const barTone = (level: string): "danger" | "warning" | "success" | "accent" =>
  level === "HIGH" ? "danger" : level === "MEDIUM" ? "warning" : level === "LOW" ? "success" : "accent";

export default function RiskPage() {
  const [signals, setSignals] = useState<SignalState>(EMPTY);
  const [result, setResult] = useState<RiskResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const setField = (key: keyof SignalState) => (value: string) =>
    setSignals((s) => ({ ...s, [key]: value }));

  const compute = async () => {
    setLoading(true);
    setError(null);
    try {
      const input: Record<string, number> = {};
      for (const { key } of FIELDS) {
        const raw = signals[key];
        if (raw !== "" && raw != null) input[key] = Number(raw);
      }
      setResult(await api.analytics.risk(input));
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError("network", "Unexpected error."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Risk"
        description="Unified 0–100 risk score across freight, port, weather, ETA, demurrage, commodity, FX and geopolitical factors. Unknown signals stay UNKNOWN — never invented."
        actions={
          <button className="btn btn--primary" onClick={compute} disabled={loading}>
            {loading ? "Scoring…" : "Score risk"}
          </button>
        }
      />

      <div className="risk-layout">
        <Card title="Risk signals" subtitle="Leave blank to mark UNKNOWN">
          <div className="risk-form">
            {FIELDS.map((f) => (
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

        <div className="risk-result">
          {loading ? (
            <Card><Loading fill label="Scoring risk…" /></Card>
          ) : error ? (
            <Card><ErrorState onRetry={compute} message={error.displayMessage} /></Card>
          ) : !result ? (
            <Card>
              <EmptyState
                icon="🛡"
                title="No score yet"
                message="Provide your risk signals on the left and score to see the overall risk and its factor breakdown."
              />
            </Card>
          ) : (
            <>
              <StatTile
                label="Overall risk score"
                value={result.overall_score.toFixed(1)}
                badge={<Badge variant={levelVariant(result.risk_level)}>{result.risk_level}</Badge>}
                note={`${result.unknown_factors.length} factor(s) unknown and excluded`}
              />
              <Card title="Factor breakdown">
                {result.factors.map((f) => (
                  <ScoreBar
                    key={f.factor}
                    label={humanize(f.factor)}
                    value={f.available ? f.contribution : null}
                    max={100}
                    unknown={!f.available}
                    tone={barTone(result.risk_level)}
                    note={f.note}
                  />
                ))}
              </Card>
            </>
          )}
        </div>
      </div>
    </>
  );
}
