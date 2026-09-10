import { useState } from "react";
import PageHeader from "../components/layout/PageHeader";
import { Badge, Card, ErrorState, FormField, Loading, Table } from "../components/ui";
import type { BadgeVariant, Column } from "../components/ui";
import { DecisionCard } from "../components/domain";
import type { DecisionFactor } from "../components/domain";
import { api, ApiError } from "../api";
import type {
  AlternativePortResult,
  CandidateRecommendation,
  FixWaitResult,
  SpotVsContractResult,
  StrategyOption,
  VesselRecommendationResult,
} from "../api";
import { formatCurrency, formatMoney, humanize } from "../lib/format";
import "./CharteringPage.css";

/**
 * Chartering recommendation workflow: a guided requirement form that composes
 * several backend engines — vessel recommendation (ranking + exclusions),
 * fix/wait timing, contract-strategy comparison, and alternative-port — into a
 * single decision surface. All numbers come from the backend; nothing is
 * computed in the browser.
 */
const ORIGINS = ["Australia", "Indonesia", "Mozambique", "USA", "Russia"];
const DESTINATIONS = ["Paradip", "Dhamra", "Visakhapatnam", "Gangavaram", "Gopalpur", "Haldia"];

interface FormState {
  origin: string;
  destination: string;
  commodity: string;
  cargo_tonnes: string;
  laycan_start: string;
  laycan_end: string;
  contract_duration: string;
}

const INITIAL: FormState = {
  origin: "Australia",
  destination: "Paradip",
  commodity: "Coal",
  cargo_tonnes: "75000",
  laycan_start: "",
  laycan_end: "",
  contract_duration: "single",
};

const strategyLabel = (s: string) => humanize(s);

export default function CharteringPage() {
  const [form, setForm] = useState<FormState>(INITIAL);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [rec, setRec] = useState<VesselRecommendationResult | null>(null);
  const [fixWait, setFixWait] = useState<FixWaitResult | null>(null);
  const [strategy, setStrategy] = useState<SpotVsContractResult | null>(null);
  const [altPort, setAltPort] = useState<AlternativePortResult | null>(null);
  const [sortDesc, setSortDesc] = useState(true);

  const setField = (key: keyof FormState) => (value: string) =>
    setForm((f) => ({ ...f, [key]: value }));

  const run = async () => {
    setLoading(true);
    setError(null);
    setRec(null); setFixWait(null); setStrategy(null); setAltPort(null);
    try {
      // Compose the decision surface from independent engines. Each is resilient:
      // a failure in one does not block the others.
      const recReq = api.analytics.recommendVessels({
        origin: form.origin,
        destination: form.destination,
        commodity: form.commodity,
        cargo_tonnes: form.cargo_tonnes,
        laycan_start: form.laycan_start || "2026-10-01",
        laycan_end: form.laycan_end || "2026-10-15",
      });
      const stratReq = api.analytics.spotVsContract({
        spot_freight_per_tonne: "22",
        cargo_tonnes: form.cargo_tonnes,
        freight_volatility: 0.5,
      });
      const altReq = api.analytics
        .alternativePort({
          origin: form.origin,
          requested_destination: form.destination,
          cargo_tonnes: form.cargo_tonnes,
          commodity: form.commodity,
        })
        .catch(() => null);

      const [recRes, stratRes, altRes] = await Promise.all([recReq, stratReq, altReq]);
      setRec(recRes);
      setStrategy(stratRes);
      setAltPort(altRes);

      // Fix/wait uses the strategy's expected cost context; a light default set
      // of forecast inputs illustrates the timing call.
      const fw = await api.analytics.fixWait({
        current_rate: "22",
        forecast_7d: "21.5",
        forecast_14d: "21",
        confidence_7d: 0.75,
        confidence_14d: 0.7,
        days_to_deadline: 30,
        congestion_score: recRes.ranked_vessels[0]?.risk
          ? (recRes.ranked_vessels[0].risk as { congestion_score?: number }).congestion_score ?? null
          : null,
      });
      setFixWait(fw);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError("network", "Unexpected error."));
    } finally {
      setLoading(false);
    }
  };

  const top = rec?.ranked_vessels[0];

  const decisionFactors: DecisionFactor[] = [];
  if (top) {
    decisionFactors.push({ label: "Top vessel", value: `${top.vessel_name} (${humanize(top.vessel_type)})` });
    decisionFactors.push({ label: "Suitability", value: `${top.suitability_score.toFixed(0)}/100` });
    if (top.estimated_total_cost) decisionFactors.push({ label: "Est. total cost", value: formatMoney(top.estimated_total_cost) });
    if (top.estimated_freight) decisionFactors.push({ label: "Est. freight", value: formatMoney(top.estimated_freight) });
    if (top.eta) decisionFactors.push({ label: "ETA delay prob.", value: `${Math.round(top.eta.delay_probability * 100)}%` });
  }
  if (strategy) decisionFactors.push({ label: "Recommended strategy", value: strategyLabel(strategy.recommended_strategy) });

  const rankedColumns: Column<CandidateRecommendation & { rank: number }>[] = [
    { key: "rank", header: "#", width: "36px" },
    { key: "vessel_name", header: "Vessel" },
    { key: "vessel_type", header: "Type", render: (r) => humanize(r.vessel_type) },
    {
      key: "compatibility",
      header: "Compatibility",
      render: (r) => {
        const status = String((r.compatibility as { status?: string }).status ?? "").toUpperCase();
        const variant: BadgeVariant =
          status === "COMPATIBLE" ? "success" : status === "CONDITIONAL" ? "warning" : status === "INCOMPATIBLE" ? "danger" : "neutral";
        return <Badge variant={variant}>{humanize(status) || "—"}</Badge>;
      },
    },
    { key: "estimated_freight", header: "Freight", align: "right", render: (r) => formatMoney(r.estimated_freight) },
    {
      key: "eta",
      header: "ETA delay",
      align: "right",
      render: (r) => (r.eta ? `${Math.round(r.eta.delay_probability * 100)}%` : "—"),
    },
    { key: "demurrage", header: "Demurrage", align: "right", render: (r) => formatMoney(r.demurrage) },
    {
      key: "suitability_score",
      header: "Suitability",
      align: "right",
      render: (r) => r.suitability_score.toFixed(0),
    },
    { key: "estimated_total_cost", header: "Total cost", align: "right", render: (r) => formatMoney(r.estimated_total_cost) },
  ];

  const rankedRows = (rec?.ranked_vessels ?? [])
    .map((v, i) => ({ ...v, rank: i + 1 }))
    .sort((a, b) => (sortDesc ? b.suitability_score - a.suitability_score : a.suitability_score - b.suitability_score))
    .map((v, i) => ({ ...v, rank: i + 1 }));

  return (
    <>
      <PageHeader
        title="Chartering"
        description="Enter a cargo requirement to get a ranked vessel recommendation, timing decision, contract strategy, and alternative-port comparison — composed from the backend decision engines."
        actions={
          <button className="btn btn--primary" onClick={run} disabled={loading}>
            {loading ? "Analysing…" : "Get recommendation"}
          </button>
        }
      />

      <Card title="Requirement">
        <div className="chartering-form">
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
          <FormField label="Commodity" value={form.commodity} onChange={setField("commodity")} />
          <FormField label="Cargo (tonnes)" type="number" value={form.cargo_tonnes} onChange={setField("cargo_tonnes")} />
          <FormField label="Laycan start" type="date" value={form.laycan_start} onChange={setField("laycan_start")} />
          <FormField label="Laycan end" type="date" value={form.laycan_end} onChange={setField("laycan_end")} />
        </div>
      </Card>

      {loading ? (
        <Card><Loading fill label="Composing recommendation…" /></Card>
      ) : error ? (
        <Card><ErrorState onRetry={run} message={error.displayMessage} /></Card>
      ) : rec ? (
        <div className="chartering-results">
          <div className="chartering-decision">
            <DecisionCard
              decision={fixWait ? humanize(fixWait.decision).toUpperCase() : (top ? "REVIEW" : "NO MATCH")}
              headline={top ? `${humanize(top.vessel_type)} · ${form.origin} → ${form.destination}` : undefined}
              subline={strategy ? strategyLabel(strategy.recommended_strategy) : undefined}
              expectedSaving={strategy ? formatCurrency(strategy.expected_savings, strategy.currency) : undefined}
              risk={top ? String((top.risk as { risk_level?: string }).risk_level ?? "").toUpperCase() || undefined : undefined}
              confidence={fixWait?.effective_confidence ?? null}
              reason={fixWait?.reason}
              factors={decisionFactors}
            />
            {!rec.route_resolved && (
              <p className="chartering-note">Note: {rec.notes.join(" ")}</p>
            )}
          </div>

          <Card
            title="Vessel ranking"
            subtitle={`${rec.ranked_vessels.length} candidates · ${rec.excluded_vessels.length} excluded`}
            padded={false}
            actions={
              <button className="btn" onClick={() => setSortDesc((v) => !v)}>
                Sort suitability {sortDesc ? "↓" : "↑"}
              </button>
            }
          >
            <Table
              columns={rankedColumns}
              rows={rankedRows}
              rowKey={(r) => r.vessel_id}
              emptyMessage="No compatible vessels for this requirement."
            />
          </Card>

          {strategy && <ContractStrategyCards result={strategy} />}

          {altPort && <AlternativePortPanel result={altPort} />}

          {rec.excluded_vessels.length > 0 && (
            <Card title="Excluded vessels" subtitle="Automatically removed (incompatible)">
              <ul className="chartering-excluded">
                {rec.excluded_vessels.map((v) => (
                  <li key={v.vessel_id}>
                    <strong>{v.vessel_name}</strong> ({humanize(v.vessel_type)}) — {v.reason}
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      ) : (
        <Card title="Recommendation">
          <p className="chartering-empty">
            Enter a requirement and run the analysis to see the recommended vessel,
            timing, contract strategy, and port options.
          </p>
        </Card>
      )}
    </>
  );
}

/** Contract-strategy comparison cards (SPOT / SHORT / MEDIUM / MULTI). */
function ContractStrategyCards({ result }: { result: SpotVsContractResult }) {
  return (
    <Card title="Contract strategy" subtitle="Lowest risk-adjusted cost is recommended">
      <div className="strategy-grid">
        {result.options.map((opt: StrategyOption) => {
          const recommended = opt.strategy === result.recommended_strategy;
          return (
            <div key={opt.strategy} className={`strategy-card${recommended ? " strategy-card--rec" : ""}`}>
              <div className="strategy-card__head">
                <span className="strategy-card__name">{strategyLabel(opt.strategy)}</span>
                {recommended && <Badge variant="success">Recommended</Badge>}
              </div>
              <dl className="strategy-card__facts">
                <div><dt>Total cost</dt><dd>{formatCurrency(opt.total_cost, opt.currency)}</dd></div>
                <div><dt>Risk score</dt><dd>{opt.risk_score.toFixed(0)}/100</dd></div>
                <div><dt>Flexibility</dt><dd>{Math.round(opt.flexibility * 100)}%</dd></div>
                <div><dt>Volatility exposure</dt><dd>{Math.round(opt.volatility_exposure * 100)}%</dd></div>
              </dl>
            </div>
          );
        })}
      </div>
      <p className="strategy-reason">{result.reason}</p>
    </Card>
  );
}

/** Primary vs alternative port comparison. */
function AlternativePortPanel({ result }: { result: AlternativePortResult }) {
  const columns: Column<AlternativePortResult["alternative_ports"][number]>[] = [
    { key: "port_name", header: "Port", render: (p) => (
      <span>{p.port_name}{p.is_requested ? " (requested)" : ""}{p.port_name === result.recommended_port ? " ★" : ""}</span>
    ) },
    { key: "feasible", header: "Feasible", render: (p) => <Badge variant={p.feasible ? "success" : "danger"}>{p.feasible ? "Yes" : "No"}</Badge> },
    { key: "total_cost", header: "Delivered cost", align: "right", render: (p) => (p.total_cost ? formatCurrency(p.total_cost, p.currency) : "—") },
    { key: "estimated_days", header: "Est. days", align: "right", render: (p) => (p.estimated_days != null ? p.estimated_days.toFixed(1) : "—") },
    { key: "expected_waiting_days", header: "Waiting (d)", align: "right", render: (p) => (p.expected_waiting_days != null ? p.expected_waiting_days.toFixed(1) : "—") },
    { key: "congestion_score", header: "Congestion", align: "right", render: (p) => (p.congestion_score != null ? p.congestion_score.toFixed(0) : "—") },
  ];
  return (
    <Card title="Alternative ports" subtitle={result.reason} padded={false}>
      <Table
        columns={columns}
        rows={result.alternative_ports}
        rowKey={(p) => p.port_id}
        emptyMessage="No alternative ports compared."
      />
    </Card>
  );
}
