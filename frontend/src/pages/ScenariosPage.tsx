import { useState } from "react";
import PageHeader from "../components/layout/PageHeader";
import { Card, ErrorState, Loading } from "../components/ui";
import { DataLabel, StatTile } from "../components/domain";
import { api, ApiError } from "../api";
import type { RiskResult, VoyageEconomicsResult } from "../api";
import { formatMoney, humanize } from "../lib/format";
import "./ScenariosPage.css";

/**
 * Scenario Simulator: what-if sliders that recompute delivered voyage cost and
 * risk against a base case by calling the backend compute engines (voyage-cost
 * + risk). It NEVER mutates production data — every run is a fresh, stateless
 * computation from the slider values.
 */
interface Levers {
  freight: number; // % adjustment to freight rate
  bunker: number; // % adjustment to bunker price
  congestion: number; // absolute 0..100 congestion
  weather: number; // 0..1 weather risk
  availability: number; // 0..1 vessel availability
  demand: number; // 0..1 cargo demand (feeds volatility proxy)
}

const BASE: Levers = { freight: 0, bunker: 0, congestion: 40, weather: 0.2, availability: 0.6, demand: 0.6 };

// Documented base assumptions the levers modify (transparent, not hidden).
const BASE_FREIGHT_RATE = 22; // USD/t
const BASE_BUNKER_PRICE = 600; // USD/t
const BASE_DISTANCE_NM = 6500;
const BASE_SPEED_KN = 13;
const CARGO_TONNES = 75000;

export default function ScenariosPage() {
  const [levers, setLevers] = useState<Levers>(BASE);
  const [voyage, setVoyage] = useState<VoyageEconomicsResult | null>(null);
  const [risk, setRisk] = useState<RiskResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const set = (key: keyof Levers) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setLevers((l) => ({ ...l, [key]: Number(e.target.value) }));

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const freightRate = BASE_FREIGHT_RATE * (1 + levers.freight / 100);
      const bunkerPrice = BASE_BUNKER_PRICE * (1 + levers.bunker / 100);
      const [voyageRes, riskRes] = await Promise.all([
        api.analytics.voyageCost({
          distance_nm: BASE_DISTANCE_NM,
          speed_kn: BASE_SPEED_KN,
          cargo_tonnes: CARGO_TONNES,
          bunker_rate_tpd: 45,
          bunker_price_per_tonne: bunkerPrice.toFixed(2),
          freight_rate_per_tonne: freightRate.toFixed(2),
          port_cost: "150000",
          port_days: (levers.congestion / 100) * 6, // congestion → waiting days
        }),
        api.analytics.risk({
          freight_volatility: Math.min(1, 0.3 + levers.demand * 0.5),
          port_congestion: levers.congestion,
          weather_risk: levers.weather,
        }),
      ]);
      setVoyage(voyageRes);
      setRisk(riskRes);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError("network", "Unexpected error."));
    } finally {
      setLoading(false);
    }
  };

  const reset = () => { setLevers(BASE); setVoyage(null); setRisk(null); };

  const sliders: Array<{ key: keyof Levers; label: string; min: number; max: number; step: number; fmt: (v: number) => string }> = [
    { key: "freight", label: "Freight rate", min: -50, max: 50, step: 5, fmt: (v) => `${v > 0 ? "+" : ""}${v}%` },
    { key: "bunker", label: "Bunker price", min: -50, max: 50, step: 5, fmt: (v) => `${v > 0 ? "+" : ""}${v}%` },
    { key: "congestion", label: "Port congestion", min: 0, max: 100, step: 5, fmt: (v) => `${v}/100` },
    { key: "weather", label: "Weather risk", min: 0, max: 1, step: 0.05, fmt: (v) => v.toFixed(2) },
    { key: "availability", label: "Vessel availability", min: 0, max: 1, step: 0.05, fmt: (v) => v.toFixed(2) },
    { key: "demand", label: "Cargo demand", min: 0, max: 1, step: 0.05, fmt: (v) => v.toFixed(2) },
  ];

  return (
    <>
      <PageHeader
        title="Scenario Simulator"
        description="Adjust market levers and recompute the delivered voyage cost and risk against a documented base case. Stateless what-if — production data is never modified."
        actions={
          <>
            <button className="btn" onClick={reset}>Reset</button>
            <button className="btn btn--primary" onClick={run} disabled={loading}>{loading ? "Running…" : "Run scenario"}</button>
          </>
        }
      />

      <div className="scenario-layout">
        <Card title="Levers" subtitle="What-if adjustments">
          <div className="scenario-sliders">
            {sliders.map((s) => (
              <label key={s.key} className="scenario-slider">
                <span className="scenario-slider__label">{s.label}<em>{s.fmt(levers[s.key])}</em></span>
                <input type="range" min={s.min} max={s.max} step={s.step} value={levers[s.key]} onChange={set(s.key)} />
              </label>
            ))}
          </div>
          <p className="scenario-base">
            Base case: freight ${BASE_FREIGHT_RATE}/t, bunker ${BASE_BUNKER_PRICE}/t,
            {" "}{BASE_DISTANCE_NM} nm @ {BASE_SPEED_KN} kn, {CARGO_TONNES.toLocaleString()} t.
          </p>
        </Card>

        <div className="scenario-result">
          {loading ? (
            <Card><Loading fill label="Recomputing…" /></Card>
          ) : error ? (
            <Card><ErrorState onRetry={run} message={error.displayMessage} /></Card>
          ) : voyage && risk ? (
            <>
              <div className="scenario-stats">
                <StatTile label="Total voyage cost" value={formatMoney(voyage.total_voyage_cost)} />
                <StatTile label="Cost per tonne" value={formatMoney(voyage.cost_per_tonne)} />
                <StatTile label="Total days" value={voyage.total_days} />
                <StatTile
                  label="Risk score"
                  value={risk.overall_score.toFixed(0)}
                  note={humanize(risk.risk_level)}
                />
              </div>
              <Card title="Cost components">
                <ul className="scenario-components">
                  {Object.entries(voyage.cost_components).map(([name, m]) => (
                    <li key={name}><span>{humanize(name)}</span><strong>{formatMoney(m)}</strong></li>
                  ))}
                </ul>
              </Card>
            </>
          ) : (
            <Card title="Impact">
              <p className="scenario-empty">
                <DataLabel kind="ESTIMATED" /> Adjust the levers and run the scenario
                to see the impact on delivered cost and risk.
              </p>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
