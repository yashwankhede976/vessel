import { useState } from "react";
import PageHeader from "../components/layout/PageHeader";
import { Badge, Card, ErrorState, FormField, Loading } from "../components/ui";
import { DataLabel, DecisionCard, ScoreBar, StatTile } from "../components/domain";
import type { DecisionFactor } from "../components/domain";
import { api, ApiError } from "../api";
import type { DecisionResult } from "../api";
import { formatMoney, humanize } from "../lib/format";
import "./DecisionPage.css";

/**
 * The unified Decision page. One requirement form → POST /decision/, which
 * composes every engine. The page lays the answer out as MARKET · FORECAST ·
 * VESSEL · PORT · ETA · COST · RISK · CONTRACT, with the final RECOMMENDATION
 * (the DecisionCard) made highly visible at the top. Scenario levers re-run the
 * same stateless what-if. Every value comes from the backend.
 */
const ORIGINS = ["Australia", "Indonesia", "Mozambique", "USA", "Russia"];
const DESTINATIONS = ["Paradip", "Dhamra", "Visakhapatnam", "Gangavaram", "Gopalpur", "Haldia"];

interface FormState {
  commodity: string;
  cargo_quantity: string;
  origin: string;
  destination: string;
  laycan_start: string;
  laycan_end: string;
  required_arrival: string;
  freight_change_pct: string;
  congestion_score: string;
  vessel_availability: string;
}

const INITIAL: FormState = {
  commodity: "Coal",
  cargo_quantity: "75000",
  origin: "Australia",
  destination: "Paradip",
  laycan_start: "",
  laycan_end: "",
  required_arrival: "",
  freight_change_pct: "",
  congestion_score: "",
  vessel_availability: "",
};

export default function DecisionPage() {
  const [form, setForm] = useState<FormState>(INITIAL);
  const [result, setResult] = useState<DecisionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const setField = (key: keyof FormState) => (value: string) =>
    setForm((f) => ({ ...f, [key]: value }));

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const scenario: Record<string, number> = {};
      if (form.freight_change_pct !== "") scenario.freight_change_pct = Number(form.freight_change_pct);
      if (form.congestion_score !== "") scenario.congestion_score = Number(form.congestion_score);
      if (form.vessel_availability !== "") scenario.vessel_availability = Number(form.vessel_availability);
      const res = await api.decision.evaluate({
        commodity: form.commodity,
        cargo_quantity: form.cargo_quantity,
        origin: form.origin,
        destination: form.destination,
        laycan_start: form.laycan_start || "2026-10-01",
        laycan_end: form.laycan_end || "2026-10-15",
        required_arrival: form.required_arrival || null,
        scenario: Object.keys(scenario).length ? scenario : undefined,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError("network", "Unexpected error."));
    } finally {
      setLoading(false);
    }
  };

  const v = result?.recommended_vessel ?? null;

  const factors: DecisionFactor[] = [];
  if (result) {
    if (v) {
      factors.push({ label: "Top vessel", value: `${v.vessel_name} (${humanize(v.vessel_type)})` });
      factors.push({ label: "Suitability", value: `${v.suitability_score.toFixed(0)}/100` });
    }
    factors.push({ label: "Market", value: `${result.market.classification} (${result.market.index.toFixed(0)})` });
    factors.push({ label: "Contract", value: humanize(result.recommended_contract.recommended_strategy) });
    factors.push({ label: "Risk", value: `${result.risk.overall_score.toFixed(0)}/100 ${result.risk.risk_level}` });
  }

  return (
    <>
      <PageHeader
        title="Decision"
        description="One requirement → the full recommendation. Composes market, forecast, vessel, port, ETA, cost, contract and risk into a single explainable decision."
        actions={
          <button className="btn btn--primary" onClick={run} disabled={loading}>
            {loading ? "Deciding…" : "Run decision"}
          </button>
        }
      />

      <Card title="Requirement">
        <div className="decision-form">
          <FormField label="Commodity" value={form.commodity} onChange={setField("commodity")} />
          <FormField label="Cargo (tonnes)" type="number" value={form.cargo_quantity} onChange={setField("cargo_quantity")} />
          <FormField label="Origin">
            {(id) => (
              <select id={id} className="ui-field__input" value={form.origin} onChange={(e) => setField("origin")(e.target.value)}>
                {ORIGINS.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            )}
          </FormField>
          <FormField label="Destination">
            {(id) => (
              <select id={id} className="ui-field__input" value={form.destination} onChange={(e) => setField("destination")(e.target.value)}>
                {DESTINATIONS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            )}
          </FormField>
          <FormField label="Laycan start" type="date" value={form.laycan_start} onChange={setField("laycan_start")} />
          <FormField label="Laycan end" type="date" value={form.laycan_end} onChange={setField("laycan_end")} />
          <FormField label="Required arrival" type="date" value={form.required_arrival} onChange={setField("required_arrival")} />
        </div>
        <details className="decision-scenario">
          <summary>Scenario (what-if — does not change stored data)</summary>
          <div className="decision-form">
            <FormField label="Freight change (%)" type="number" hint="e.g. 10 or -10" value={form.freight_change_pct} onChange={setField("freight_change_pct")} />
            <FormField label="Congestion (0–100)" type="number" value={form.congestion_score} onChange={setField("congestion_score")} />
            <FormField label="Vessel availability (0–1)" type="number" value={form.vessel_availability} onChange={setField("vessel_availability")} />
          </div>
        </details>
      </Card>

      {loading ? (
        <Card><Loading fill label="Composing the decision…" /></Card>
      ) : error ? (
        <Card><ErrorState onRetry={run} message={error.displayMessage} /></Card>
      ) : result ? (
        <div className="decision-results">
          {/* RECOMMENDATION — highly visible */}
          <DecisionCard
            decision={humanize(result.timing_decision).toUpperCase()}
            headline={v ? `${humanize(v.vessel_type)} · ${form.origin} → ${form.destination}` : `${form.origin} → ${form.destination}`}
            subline={humanize(result.recommended_contract.recommended_strategy)}
            expectedSaving={result.expected_savings ? formatMoney({ amount: result.expected_savings.amount, currency: result.expected_savings.currency, unit: "total" }) : undefined}
            risk={result.risk.risk_level}
            confidence={result.confidence}
            reason={result.timing.reason}
            factors={factors}
          />

          {result.notes.length > 0 && (
            <p className="decision-note">{result.notes.join(" ")}</p>
          )}

          {/* Section grid: MARKET / FORECAST / VESSEL / PORT / ETA / COST / RISK / CONTRACT */}
          <div className="decision-grid">
            <Section title="Market" label="ESTIMATED">
              <StatTile label="Pressure index" value={result.market.index.toFixed(0)} note={humanize(result.market.classification)} />
            </Section>

            <Section title="Forecast" label="FORECAST">
              <dl className="decision-dl">
                <Row k="Working rate/t" val={result.freight_forecast.working_rate ? `$${result.freight_forecast.working_rate}` : "—"} />
                <Row k="Band low–high" val={result.freight_forecast.band.low ? `$${result.freight_forecast.band.low} – $${result.freight_forecast.band.high}` : "—"} />
                <Row k="Model" val={result.freight_forecast.freight_model ? `${result.freight_forecast.freight_model} ${result.freight_forecast.freight_model_version ?? ""}` : result.freight_forecast.source} />
              </dl>
            </Section>

            <Section title="Vessel" label={v ? "REAL" : "UNKNOWN"}>
              {v ? (
                <dl className="decision-dl">
                  <Row k="Recommended" val={`${v.vessel_name} (${humanize(v.vessel_type)})`} />
                  <Row k="IMO" val={v.imo} />
                  <Row k="Suitability" val={`${v.suitability_score.toFixed(0)}/100`} />
                </dl>
              ) : <p className="decision-empty">No compatible open vessel found.</p>}
            </Section>

            <Section title="Port" label="REAL">
              <dl className="decision-dl">
                <Row k="Destination" val={form.destination} />
                <Row k="Compatibility" val={result.compatibility ? humanize(String((result.compatibility as { status?: string }).status ?? "—")) : "—"} />
                <Row k="Congestion" val={result.congestion?.score != null ? `${result.congestion.score.toFixed(0)}/100` : "—"} />
              </dl>
            </Section>

            <Section title="ETA" label="FORECAST">
              {result.eta ? (
                <dl className="decision-dl">
                  <Row k="ETA (point)" val={new Date(result.eta.eta).toLocaleDateString()} />
                  <Row k="P80" val={new Date(result.eta.eta_p80).toLocaleDateString()} />
                  <Row k="Delay prob." val={`${Math.round(result.eta.delay_probability * 100)}%`} />
                </dl>
              ) : <p className="decision-empty">ETA needs a route with distance.</p>}
            </Section>

            <Section title="Cost" label="ESTIMATED">
              <dl className="decision-dl">
                <Row k="Total voyage cost" val={formatMoney(result.total_landed_cost)} />
                <Row k="Demurrage" val={formatMoney(result.demurrage)} />
                <Row k="Expected saving" val={result.expected_savings ? formatMoney({ amount: result.expected_savings.amount, currency: result.expected_savings.currency, unit: "total" }) : "—"} />
              </dl>
            </Section>

            <Section title="Risk" label="ESTIMATED">
              <StatTile
                label="Overall risk"
                value={result.risk.overall_score.toFixed(0)}
                badge={<Badge variant={result.risk.risk_level === "HIGH" ? "danger" : result.risk.risk_level === "MEDIUM" ? "warning" : "success"}>{result.risk.risk_level}</Badge>}
              />
            </Section>

            <Section title="Contract" label="ESTIMATED">
              <dl className="decision-dl">
                <Row k="Recommended" val={humanize(result.recommended_contract.recommended_strategy)} />
                <Row k="Expected cost" val={`$${result.recommended_contract.expected_cost}`} />
                <Row k="Timing" val={humanize(result.timing_decision)} />
              </dl>
            </Section>
          </div>

          {/* Explainability */}
          <div className="decision-grid decision-grid--why">
            <Card title="Why this recommendation" subtitle="Reasons">
              <ul className="decision-list">{result.explainability.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </Card>
            <Card title="Positive factors">
              <ul className="decision-list decision-list--pos">{result.explainability.positive_factors.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </Card>
            <Card title="Negative factors">
              <ul className="decision-list decision-list--neg">{result.explainability.negative_factors.length ? result.explainability.negative_factors.map((r, i) => <li key={i}>{r}</li>) : <li>None flagged.</li>}</ul>
            </Card>
          </div>

          <Card title="Risk factor breakdown">
            {result.risk.factors.map((f) => (
              <ScoreBar
                key={f.factor}
                label={humanize(f.factor)}
                value={f.available ? f.contribution : null}
                max={100}
                unknown={!f.available}
                tone={result.risk.risk_level === "HIGH" ? "danger" : result.risk.risk_level === "MEDIUM" ? "warning" : "success"}
                note={f.note}
              />
            ))}
          </Card>
        </div>
      ) : (
        <Card title="Recommendation">
          <p className="decision-empty">
            <DataLabel kind="ESTIMATED" /> Enter a requirement and run the decision
            to see the full recommendation.
          </p>
        </Card>
      )}
    </>
  );
}

function Section({ title, label, children }: { title: string; label: string; children: React.ReactNode }) {
  return (
    <Card
      title={<span className="decision-section-title">{title}</span>}
      actions={<DataLabel kind={label as "REAL" | "ESTIMATED" | "FORECAST" | "UNKNOWN"} />}
    >
      {children}
    </Card>
  );
}

function Row({ k, val }: { k: string; val: string }) {
  return (
    <div className="decision-dl__row">
      <dt>{k}</dt>
      <dd>{val}</dd>
    </div>
  );
}
